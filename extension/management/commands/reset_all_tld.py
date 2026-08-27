from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from extension.models import TldRecord
import pandas as pd


class Command(BaseCommand):
    help = 'Registers all Top Level Domains (TLDs) for Interventions / URL tracking by commandline from the data/all_tlds.csv file. Expect columns tld, apply_intervention, apply_collect_links to see.'

    def handle(self, *args, **options):
        result = finders.find('data/all_tlds.csv')
        if result is None:
            raise CommandError(f'Error, data/benkler_tlds.csv not found.')
        
        all_tld_df = pd.read_csv(result)
        if 'tld' not in all_tld_df.columns or 'apply_intervention' not in all_tld_df.columns or 'apply_collect_links' not in all_tld_df.columns:
            raise CommandError(f'Error, columns missing, these columns present instead: {all_tld_df.columns}')

        # Delete and register
        TldRecord.objects.all().delete()
        for row in all_tld_df.itertuples(index=False):
            new_tld = TldRecord(tld=row.tld, apply_intervention=row.apply_intervention, apply_collect_links=row.apply_collect_links)
            new_tld.save()
        
        return f'Finished registering all new Benkler TLD codes!'
