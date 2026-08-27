from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from onboard.models import ZipCodeInfo
import pandas as pd


class Command(BaseCommand):
    help = 'Registers all zipcode values based on $STATIC/data/zip_code_database.csv'

    def handle(self, *args, **options):
        result = finders.find('data/zip_code_database.csv')
        if result is None:
            raise CommandError(f'Error, data/zip_code_database.csv not found.')
        
        zipcode_df = pd.read_csv(result, converters={'zip': lambda x: str(x)})
        total_rows = zipcode_df.shape[0]
        row = 0
        skipped_rows = False
        skip_size = 10

        while row < total_rows:
            zipcode_str = zipcode_df.loc[row, 'zip']
            
            if ZipCodeInfo.objects.filter(zip=zipcode_str).count():
                self.stdout.write(f'Zipcode {zipcode_str} already exists!')
                skipped_rows = True
                if row + skip_size < total_rows:
                    row += skip_size
                else:
                    skip_size = 1
                    row += skip_size
                continue
            else:
                if skipped_rows:
                    row -= skip_size + 1
                    skip_size = 1
                    skipped_rows = False

            new_zipcode_obj = ZipCodeInfo(
                zip = zipcode_str, 
                zip_type = zipcode_df.loc[row, 'type'],
                is_decommissioned = bool(zipcode_df.loc[row, 'decommissioned']),
                primary_city = zipcode_df.loc[row, 'primary_city'],
                state =  zipcode_df.loc[row, 'state'],
                county =  zipcode_df.loc[row, 'county'],
                latitude =  zipcode_df.loc[row, 'latitude'],
                longitude =  zipcode_df.loc[row, 'longitude']
            )
            new_zipcode_obj.save()
            row += 1
        
        return f'Finished registering all zipcodes!'
