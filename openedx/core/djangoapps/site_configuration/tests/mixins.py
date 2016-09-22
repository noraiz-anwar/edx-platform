from openedx.core.djangoapps.site_configuration.tests.factories import SiteConfigurationFactory, SiteFactory


class SiteMixin(object):
    def setUp(self):
        super(SiteMixin, self).setUp()

        self.site = SiteFactory.create()
        self.site_configuration = SiteConfigurationFactory.create(
            site=self.site,
            values={
                "SITE_NAME": self.site.domain,
                "course_org_filter": "fakeX",
            }
        )

        # Set the domain used for all test requests
        self.client = self.client_class(SERVER_NAME=self.site.domain)
