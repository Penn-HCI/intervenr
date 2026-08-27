from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from extension.models import TldRecord
import pandas as pd


class Command(BaseCommand):
    help = 'Registers all Top Level Domains (TLDs) for Interventions / URL tracking by commandline from the data/social_tlds.csv file.'

    def handle(self, *args, **options):
        result = finders.find('data/social_tlds.csv')
        if result is None:
            raise CommandError(f'Error, data/social_tlds.csv not found.')
        
        benkler_tld_df = pd.read_csv(result)
        for row in benkler_tld_df.itertuples(index=False):
            if TldRecord.objects.filter(tld=row.tld):
                self.stdout.write(f'SocialTld {row.tld} already exists!')
                continue

            new_tld = TldRecord(tld=row.tld, apply_intervention=False, apply_collect_links=True)
            new_tld.save()
        
        return f'Finished registering all new Social TLD codes!'
