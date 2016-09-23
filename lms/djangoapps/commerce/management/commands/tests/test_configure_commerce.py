"""
Tests for management command for enabling commerce configuration.
"""
from django.test import TestCase
from django.core.management import call_command
from django.contrib.sites.models import Site

from commerce.models import CommerceConfiguration


class TestCommerceConfigurationCommand(TestCase):
    """
    Test django management command for enabling commerce configuration.
    """
    def setUp(self):
        super(TestCommerceConfigurationCommand, self).setUp()
        self.site, __ = Site.objects.get_or_create(domain="test.localhost", defaults={"name": "test.localhost"})

    def test_commerce_configuration(self):
        """
        Test that commerce configuration is created properly.
        """
        call_command(
            "configure_commerce",
            "--site-domain=test.localhost",
        )

        # Verify commerce configuration is enabled with appropriate values
        commerce_configuration = CommerceConfiguration.current()

        self.assertEqual(commerce_configuration.site.domain, "test.localhost")
        self.assertTrue(commerce_configuration.enabled)
        self.assertTrue(commerce_configuration.checkout_on_ecommerce_service)
        self.assertEqual(commerce_configuration.single_course_checkout_page, "/basket/single-item/")
        self.assertEqual(commerce_configuration.cache_ttl, 0)

        # Verify commerce configuration can be disabled from command
        call_command(
            "configure_commerce",
            "--site-domain=test.localhost",
            '--disable',
        )

        commerce_configuration = CommerceConfiguration.current()
        self.assertFalse(commerce_configuration.enabled)

        # Verify commerce configuration can be disabled from command
        call_command(
            "configure_commerce",
            "--site-domain=test.localhost",
            '--disable-checkout-on-ecommerce',
        )

        commerce_configuration = CommerceConfiguration.current()
        self.assertFalse(commerce_configuration.checkout_on_ecommerce_service)

    def test_commerce_configuration_2(self):
        """
        Test that commerce configuration is created properly when there is no site is associated.
        """
        call_command(
            "configure_commerce",
        )

        # Verify commerce configuration is enabled with appropriate values
        commerce_configuration = CommerceConfiguration.current()

        self.assertIsNone(commerce_configuration.site)
        self.assertTrue(commerce_configuration.enabled)
        self.assertTrue(commerce_configuration.checkout_on_ecommerce_service)
        self.assertEqual(commerce_configuration.single_course_checkout_page, "/basket/single-item/")
        self.assertEqual(commerce_configuration.cache_ttl, 0)

        # Verify site can be associated to a configuration after its creation
        call_command(
            "configure_commerce",
            "--site-domain=test.localhost",
            '--disable',
        )

        commerce_configuration = CommerceConfiguration.current()
        self.assertFalse(commerce_configuration.enabled)

        # Verify commerce configuration can be disabled from command and site association can be removed
        call_command(
            "configure_commerce",
            '--disable-checkout-on-ecommerce',
        )

        commerce_configuration = CommerceConfiguration.current()
        self.assertIsNone(commerce_configuration.site)
        self.assertFalse(commerce_configuration.checkout_on_ecommerce_service)
