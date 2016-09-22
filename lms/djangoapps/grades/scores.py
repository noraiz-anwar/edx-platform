"""
Functionality for problem scores.
"""
from logging import getLogger

from openedx.core.lib.cache_utils import memoized
from xblock.core import XBlock
from xmodule import block_metadata_utils
from xmodule.graders import ProblemScore
from .transformer import GradesTransformer


log = getLogger(__name__)


@memoized
def block_types_possibly_scored():
    """
    Returns the block types that could have a score.

    Something might be a scored item if it is capable of storing a score
    (has_score=True). We also have to include anything that can have children,
    since those children might have scores. We can avoid things like Videos,
    which have state but cannot ever impact someone's grade.
    """
    return frozenset(
        cat for (cat, xblock_class) in XBlock.load_classes() if (
            getattr(xblock_class, 'has_score', False) or getattr(xblock_class, 'has_children', False)
        )
    )


def possibly_scored(usage_key):
    """
    Returns whether the given block could impact grading (i.e. scored, or has children).
    """
    return usage_key.block_type in block_types_possibly_scored()


def weighted_score(raw_earned, raw_possible, weight=None):
    """
    Return a tuple that represents the weighted (earned, possible) score.
    If weight is None or raw_possible is 0, returns the original values.
    """
    if weight is None or raw_possible == 0:
        return raw_earned, raw_possible
    else:
        return float(raw_earned) * weight / raw_possible, float(weight)


def get_score(scores_client, submissions_scores_cache, block, persisted_block=None):
    """
    Return the score for a user on a problem, as a tuple (earned, possible).
    e.g. (5,7) if you got 5 out of 7 points.

    If this problem doesn't have a score, or we couldn't load it, returns (None,
    None).

    user: a Student object
    scores_client: an initialized ScoresClient
    submissions_scores_cache: A dict of location names to (earned, possible)
        point tuples.  If an entry is found in this cache, it takes precedence.
    block: a BlockStructure's BlockData object
    persisted_block: a BlockRecord, if found from the database.
    """
    weight = block.weight if persisted_block else getattr(block, 'weight', None)

    r_earned, r_possible, w_earned, w_possible = (
        _get_from_submissions(submissions_scores_cache, block) or
        _get_from_courseware_student_module(scores_client, block, weight) or
        _get_from_block(persisted_block, block, weight)
    )

    if w_earned is not None or w_possible is not None:
        # There's a chance that the value of graded is not the same
        # value when the problem was scored. Since we get the value
        # from the block_structure.
        #
        if w_possible is not None and w_possible > 0:
            # cannot grade a problem with an invalid denominator
            graded = _get_explicit_graded(block)
        else:
            graded = False

        return ProblemScore(
            r_earned,
            r_possible,
            w_earned,
            w_possible,
            weight,
            graded,
            display_name=block_metadata_utils.display_name_with_default_escaped(block),
            module_id=block.location,
        )


def _get_from_submissions(submissions_scores_cache, block):
    """
    Returns the score values from the submissions API if found.
    """
    if submissions_scores_cache:
        submission_value = submissions_scores_cache.get(unicode(block.location))
        if submission_value:
            w_earned, w_possible = submission_value
            return (None, None) + (w_earned, w_possible)


def _get_from_courseware_student_module(scores_client, block, weight):
    """
    Returns the score values from the courseware student module, via
    ScoresClient, if found.
    """
    # If an entry exists and has a total associated with it, we trust that
    # value. This is important for cases where a student might have seen an
    # older version of the problem -- they're still graded on what was possible
    # when they tried the problem, not what it's worth now.
    score = scores_client.get(block.location)
    if score and score.total is not None:
        # We have a valid score, just use it.
        r_earned = score.correct if score.correct is not None else 0.0
        r_possible = score.total
        return (r_earned, r_possible) + weighted_score(r_earned, r_possible, weight)


def _get_from_block(persisted_block, block, weight):
    """
    Returns the score values, assuming the earned score is 0.0.
    Gets the r_possible data from the persisted_block or the
    given block, in that order.
    """
    r_earned = 0.0
    r_possible = persisted_block.r_possible if persisted_block else block.transformer_data[GradesTransformer].max_score
    if r_possible is None:
        w_earned, w_possible = None, None
    else:
        w_earned, w_possible = weighted_score(r_earned, r_possible, weight)

    return r_earned, r_possible, w_earned, w_possible


def _get_explicit_graded(block):
    """
    Returns the explicit graded field value for the given block
    """
    field_value = getattr(
        block.transformer_data[GradesTransformer],
        GradesTransformer.EXPLICIT_GRADED_FIELD_NAME,
        None,
    )

    # Set to True if grading is not explicitly disabled for
    # this block.  This allows us to include the block's score
    # in the aggregated self.graded_total, regardless of the
    # inherited graded value from the subsection. (TNL-5560)
    return True if field_value is None else field_value
