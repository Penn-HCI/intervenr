from django.core.management.base import BaseCommand, CommandError
from django.contrib.staticfiles import finders
from onboard.models import OnboardCode
import pandas as pd


class Command(BaseCommand):
    help = 'Registers all Onboard Code values by command line from the data/onboard_codes.csv file.'

    def handle(self, *args, **options):
        result = finders.find('data/onboard_code_database.csv')
        if result is None:
            raise CommandError(f'Error, data/onboard_code_database.csv not found.')
        
        onboard_code_df = pd.read_csv(result)
        for row in onboard_code_df.itertuples(index=False):
            code = row.onboard_code
            if OnboardCode.objects.filter(onboard_code=code):
                self.stdout.write(f'OnboardCode {code} already exists!')
                continue
            
            new_onboard_code = OnboardCode(onboard_code=code)
            new_onboard_code.save()
        
        return f'Finished registering all new onboarding codes!'
