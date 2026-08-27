from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from extension.models import TldRecord
import pandas as pd


class Command(BaseCommand):
    help = 'Registers all Top Level Domains (TLDs) for Interventions / URL tracking by commandline from the data/benkler_tlds.csv file.'

    def handle(self, *args, **options):
        result = finders.find('data/benkler_tlds.csv')
        if result is None:
            raise CommandError(f'Error, data/benkler_tlds.csv not found.')
        
        benkler_tld_df = pd.read_csv(result)
        for row in benkler_tld_df.itertuples(index=False):
            if TldRecord.objects.filter(tld=row.tld):
                self.stdout.write(f'BenklerTld {row.tld} already exists!')
                continue

            new_tld = TldRecord(tld=row.tld, apply_intervention=True, apply_collect_links=False)
            new_tld.save()
        
        return f'Finished registering all new Benkler TLD codes!'
