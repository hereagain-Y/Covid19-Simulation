import numpy as np

'''
Settings for town generation
'''

town_name = 'Locarno'
country = 'CH'

# Make sure to download country-specific population density data
# from https://data.humdata.org/organization/facebook
population_path = 'lib/data/population/population_che_2019-07-01.csv'   # Population density file

sites_path='lib/data/queries/' # Directory containing OSM site query details
bbox = (46.1555, 46.1942, 8.7678, 8.8122) # Coordinate bounding box

# Population per age group in the region
# Source: https://www.citypopulation.de/en/switzerland/admin/21__ticino/
population_per_age_group = np.array([30078,     # 0-9
                                     34020,     # 10-19
                                     37660,     # 20-29
                                     40390,     # 30-39
                                     52502,     # 40-49
                                     56937,     # 50-59
                                     41660,     # 60-69
                                     35925,     # 70-79
                                     24171      # 80+
                                     ], dtype=np.int32)

region_population = population_per_age_group.sum()
town_population = 15824

# Roughly 5k tests per day in Switzerland (rough average over time frame 10.03.-27.04.2020:
# https://www.bag.admin.ch/bag/en/home/krankheiten/ausbrueche-epidemien-pandemien/aktuelle-ausbrueche-epidemien/novel-cov/situation-schweiz-und-international.html
daily_tests_unscaled = int(5000 * (town_population / 8570000))

# Information about household structure (set to None if not available)
# Source for Switzerland: https://www.bfs.admin.ch/bfs/de/home/statistiken/bevoelkerung/stand-entwicklung/haushalte.html
household_info = {
    'size_dist': [16, 29, 18, 23, 14],              # distribution of household sizes (1-5 people) in %
    'soc_role': {
        'children': [1, 8/10, 0, 0, 0, 0, 0, 0, 0],    # age groups 0,1 can be children
        'parents': [0, 2/10, 1, 1, 1, 1, 0, 0, 0],     # age groups 1,2,3,4,5 can be parents
        'elderly': [0, 0, 0, 0, 0, 0, 1, 1, 1]         # age groups 6,7,8 are elderly
    }
}

