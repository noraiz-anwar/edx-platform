"""
CourseGrade Class
"""

from collections import defaultdict
from django.conf import settings
from lazy import lazy
from logging import getLogger
from lms.djangoapps.course_blocks.api import get_course_blocks
from lms.djangoapps.grades.config.models import PersistentGradesEnabledFlag
from openedx.core.djangoapps.signals.signals import GRADES_UPDATED
from xmodule import block_metadata_utils

from .subsection_grade import SubsectionGradeFactory


log = getLogger(__name__)


class CourseGrade(object):
    """
    Course Grade class
    """
    def __init__(self, student, course, course_structure):
        self.student = student
        self.course = course
        self.course_structure = course_structure
        self.chapter_grades = []

    @lazy
    def subsection_grade_totals_by_format(self):
        """
        Returns grades for the subsections in the course in
        a dict keyed by subsection format types.
        """
        subsections_by_format = defaultdict(list)
        for chapter in self.chapter_grades:
            for subsection_grade in chapter['sections']:
                if subsection_grade.graded:
                    graded_total = subsection_grade.graded_total
                    if graded_total.possible > 0:
                        subsections_by_format[subsection_grade.format].append(graded_total)
        self._log_event(log.info, u"subsections_by_format")
        return subsections_by_format

    @lazy
    def locations_to_scores(self):
        """
        Returns a dict of problem scores keyed by their locations.
        """
        locations_to_scores = {}
        for chapter in self.chapter_grades:
            for subsection_grade in chapter['sections']:
                locations_to_scores.update(subsection_grade.locations_to_scores)
        self._log_event(log.info, u"locations_to_scores")
        return locations_to_scores

    @lazy
    def grade_value(self):
        """
        Helper function to extract the grade value as calculated by the course's grader.
        """
        # Grading policy might be overriden by a CCX, need to reset it
        self.course.set_grading_policy(self.course.grading_policy)
        grade_value = self.course.grader.grade(
            self.subsection_grade_totals_by_format,
            generate_random_scores=settings.GENERATE_PROFILE_SCORES
        )
        self._log_event(log.info, u"grade_value")
        return grade_value

    @property
    def has_access_to_course(self):
        """
        Returns whether the course structure as seen by the
        given student is non-empty.
        """
        return len(self.course_structure) > 0

    @property
    def percent(self):
        """
        Returns a rounded percent from the overall grade.
        """
        return round(self.grade_value['percent'] * 100 + 0.05) / 100

    @property
    def letter_grade(self):
        """
        Returns a letter representing the grade.
        """
        return self._compute_letter_grade(self.percent)

    @property
    def passed(self):
        """
        Check user's course passing status. Return True if passed.
        """
        nonzero_cutoffs = [cutoff for cutoff in self.course.grade_cutoffs.values() if cutoff > 0]
        success_cutoff = min(nonzero_cutoffs) if nonzero_cutoffs else None
        return success_cutoff and self.percent >= success_cutoff

    @property
    def summary(self):
        """
        Returns the grade summary as calculated by the course's grader.
        """
        grade_summary = self.grade_value

        # We round the grade here, to make sure that the grade is a whole percentage and
        # doesn't get displayed differently than it gets grades
        grade_summary['percent'] = self.percent
        grade_summary['grade'] = self.letter_grade
        grade_summary['totaled_scores'] = self.subsection_grade_totals_by_format
        grade_summary['raw_scores'] = list(self.locations_to_scores.itervalues())

        self._log_event(log.warning, u"grade_summary, percent: {0}, grade: {1}".format(self.percent, self.letter_grade))
        return grade_summary

    def compute_and_update(self, read_only=False):
        """
        Computes the grade for the given student and course.

        If read_only is True, doesn't save any updates to the grades.
        """
        self._log_event(log.warning, u"compute_and_update, read_only: {}".format(read_only))
        subsection_grade_factory = SubsectionGradeFactory(self.student, self.course, self.course_structure)
        for chapter_key in self.course_structure.get_children(self.course.location):
            chapter = self.course_structure[chapter_key]
            chapter_subsection_grades = []
            for subsection_key in self.course_structure.get_children(chapter_key):
                chapter_subsection_grades.append(
                    subsection_grade_factory.create(self.course_structure[subsection_key], read_only=True)
                )

            self.chapter_grades.append({
                'display_name': block_metadata_utils.display_name_with_default_escaped(chapter),
                'url_name': block_metadata_utils.url_name_for_block(chapter),
                'sections': chapter_subsection_grades
            })

        if not read_only:
            subsection_grade_factory.bulk_create_unsaved()

        self._signal_listeners_when_grade_computed()

    def score_for_module(self, location):
        """
        Calculate the aggregate weighted score for any location in the course.
        This method returns a tuple containing (earned_score, possible_score).

        If the location is of 'problem' type, this method will return the
        possible and earned scores for that problem. If the location refers to a
        composite module (a vertical or section ) the scores will be the sums of
        all scored problems that are children of the chosen location.
        """
        if location in self.locations_to_scores:
            score = self.locations_to_scores[location]
            return score.earned, score.possible
        children = self.course_structure.get_children(location)
        earned = 0.0
        possible = 0.0
        for child in children:
            child_earned, child_possible = self.score_for_module(child)
            earned += child_earned
            possible += child_possible
        return earned, possible

    def _compute_letter_grade(self, percentage):
        """
        Returns a letter grade as defined in grading_policy (e.g. 'A' 'B' 'C' for 6.002x) or None.

        Arguments
        - grade_cutoffs is a dictionary mapping a grade to the lowest
            possible percentage to earn that grade.
        - percentage is the final percent across all problems in a course
        """

        letter_grade = None
        grade_cutoffs = self.course.grade_cutoffs

        # Possible grades, sorted in descending order of score
        descending_grades = sorted(grade_cutoffs, key=lambda x: grade_cutoffs[x], reverse=True)
        for possible_grade in descending_grades:
            if percentage >= grade_cutoffs[possible_grade]:
                letter_grade = possible_grade
                break

        return letter_grade

    def _signal_listeners_when_grade_computed(self):
        """
        Signal all listeners when grades are computed.
        """
        responses = GRADES_UPDATED.send_robust(
            sender=None,
            user=self.student,
            grade_summary=self.summary,
            course_key=self.course.id,
            deadline=self.course.end
        )

        for receiver, response in responses:
            log.info(
                'Signal fired when student grade is calculated. Receiver: %s. Response: %s',
                receiver, response
            )

    def _log_event(self, log_func, log_statement):
        """
        Logs the given statement, for this instance.
        """
        log_func(u"Persistent Grades: CourseGrade.{0}, course: {1}, user: {2}".format(
            log_statement,
            self.course.id,
            self.student.id
        ))


class CourseGradeFactory(object):
    """
    Factory class to create Course Grade objects
    """
    def __init__(self, student):
        self.student = student

    def create(self, course, read_only=False):
        """
        Returns the CourseGrade object for the given student and course.

        If read_only is True, doesn't save any updates to the grades.
        """
        course_structure = get_course_blocks(self.student, course.location)
        return (
            self._get_saved_grade(course, course_structure) or
            self._compute_and_update_grade(course, course_structure, read_only)
        )

    def _compute_and_update_grade(self, course, course_structure, read_only):
        """
        Freshly computes and updates the grade for the student and course.

        If read_only is True, doesn't save any updates to the grades.
        """
        course_grade = CourseGrade(self.student, course, course_structure)
        course_grade.compute_and_update(read_only)
        return course_grade

    def _get_saved_grade(self, course, course_structure):  # pylint: disable=unused-argument
        """
        Returns the saved grade for the given course and student.
        """
        if PersistentGradesEnabledFlag.feature_enabled(course.id):
            # TODO LATER Retrieve the saved grade for the course, if it exists.
            _pretend_to_save_course_grades()


def _pretend_to_save_course_grades():
    """
    Stub to facilitate testing feature flag until robust grade work lands.
    """
    pass
