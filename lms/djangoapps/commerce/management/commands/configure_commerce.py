"""
Enable or disable commerce configuration.
"""

from __future__ import unicode_literals
import logging

from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from commerce.models import CommerceConfiguration

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Command(BaseCommand):
    """
    Command to enable or disable commerce configuration
    """
    help = 'Enable or disable commerce configuration'

    def add_arguments(self, parser):
        parser.add_argument('--site-id',
                            action='store',
                            dest='site_id',
                            type=int,
                            help='ID of the Site to associate with the configuration.')
        parser.add_argument('--site-domain',
                            action='store',
                            dest='site_domain',
                            default='',
                            type=str,
                            help='Domain of the Site to associate with the configuration.')
        parser.add_argument('--disable-checkout-on-ecommerce',
                            dest='checkout_on_ecommerce',
                            action='store_false',
                            default=True,
                            help='Disable checkout to ecommerce.')
        parser.add_argument('--disable',
                            dest='disable',
                            action='store_true',
                            default=False,
                            help='Disable existing commerce configuration.')

    def handle(self, *args, **options):
        site_id = options.get('site_id')
        site_domain = options.get('site_domain')
        disable = options.get('disable')
        checkout_on_ecommerce = options.get('checkout_on_ecommerce')
        site = None

        # We need to associate site only if it is given
        if site_id or site_domain:
            try:
                site = Site.objects.get(id=site_id)
            except Site.DoesNotExist:
                site = Site.objects.get(domain=site_domain)

        # We are keeping id=1, because as of now, there are only one commerce configuration for the system.
        CommerceConfiguration.objects.update_or_create(  # pylint: disable=no-member
            id=1,
            defaults={
                "site": site,
                'enabled': not disable,
                'checkout_on_ecommerce_service': checkout_on_ecommerce,
            }
        )
        logger.info(
            'Commerce Configuration %s with checkout on ecommerce %s',
            "disabled" if disable else "enabled",
            "disabled" if checkout_on_ecommerce else "enabled",
        )
