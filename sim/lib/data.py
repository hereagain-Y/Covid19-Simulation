import sys
import argparse
if '..' not in sys.path:
    sys.path.append('..')

import time
import bisect
import numpy as np
import pandas as pd
import networkx as nx
import scipy
import scipy.optimize
import scipy as sp
import os
import matplotlib.pyplot as plt
import random

TO_HOURS = 24.0

from lib.calibrationSettings import command_line_area_codes


def get_preprocessed_data_germany(landkreis='LK Tübingen', start_date_string='2020-03-10', until=None, end_date_string=None):
    '''
    Preprocesses data for a specific Landkreis in Germany
    Data taken from
    https://npgeo-corona-npgeo-de.hub.arcgis.com/datasets/dd4580c810204019a7b8eb3e0b329dd6_0?orderBy=Bundesland

    List of Landkreis districts in `data_availability_GER.md`

    '''

    # preprocessing
    df = pd.read_csv('lib/data/cases/GER_COVID19.csv', header=0, delimiter=',')
    # print('Data last updated at: ', df.Datenstand.unique()[0])

    # delete unnecessary
    df = df[df['Landkreis'] == landkreis]
    df.drop(['Datenstand', 'IdLandkreis', 'Refdatum', 
            'Landkreis', 'IdBundesland', 'Bundesland', 'Geschlecht'], axis=1, inplace=True)

    # delete weird data rows (insignificant)
    df = df[df.Altersgruppe != 'unbekannt'] # this is just 1 row

    # Altersgruppe map
    agemap = {
        'A00-A04' : 0,
        'A05-A14' : 1,
        'A15-A34' : 2,
        'A35-A59' : 3,
        'A60-A79' : 4,
        'A80+' : 5,
    }
    df['age_group'] = 0
    for k,v in agemap.items():
        df.loc[df.Altersgruppe == k, 'age_group'] = v
    df.drop(['Altersgruppe'], axis=1, inplace=True)

    # process date to a number of days until start of actual case growth
    df.Meldedatum = pd.to_datetime(df.Meldedatum)
    start_date = pd.to_datetime(start_date_string)
    df['days'] = (df.Meldedatum - start_date).dt.days

    # filter days
    if until:
        df = df[df['days'] <= until]

    if end_date_string:
        df = df[df['Meldedatum'] <= pd.to_datetime(end_date_string)]

    return df


def get_preprocessed_data_switzerland(canton='ZH', start_date_string='2020-03-10', until=None, end_date_string=None):
    '''
    Preprocesses data for a specific Canton district in Switzerland
    Data taken from
    https://covid-19-schweiz.bagapps.ch/de-1.html

    List of Cantons districts in `data_availability_CH.md`

    '''

    # preprocessing
    df = pd.read_csv('lib/data/cases/CH_COVID19.csv',
                     header=0, delimiter='\t', encoding='utf-16')
    # print('Data last updated at: ', df.Datenstand.unique()[0])

    # delete unnecessary
    df = df[df['Canton'] == canton]
    df = df[['Canton', 'Altersklasse', 'Datum', 'Anzahl laborbestätigte Fälle']]

    # Altersgruppe map
    agemap = {
        '0 - 9 Jahren': 0,
        '10 - 19 Jahren': 1,
        '20 - 29 Jahren': 2,
        '30 - 39 Jahren': 3,
        '40 - 49 Jahren': 4,
        '50 - 59 Jahren': 5,
        '60 - 69 Jahren': 6,
        '70 - 79 Jahren': 7,
        '80+ Jahren': 8,
    }
    df['age_group'] = 0
    for k, v in agemap.items():
        df.loc[df.Altersklasse == k, 'age_group'] = v
    df.drop(['Altersklasse'], axis=1, inplace=True)

    # process date to a number of days until start of actual case growth
    df['Datum'] = pd.to_datetime(
        df['Datum'], format='%d.%m.%Y')
    # only 4 cases in 2 weeks before that
    start_date = pd.to_datetime(start_date_string)
    df['days'] = ((df['Datum'] - start_date).dt.days)
    df = df[df['days'].notna()] # drop nan dates
    df.days = df.days.astype(int) # 

    # rename into nicer column name
    df['new'] = df['Anzahl laborbestätigte Fälle']
    df.drop(['Anzahl laborbestätigte Fälle'], axis=1, inplace=True)

    # filter days
    if until:
        df = df[df['days'] <= until]

    if end_date_string:
        df = df[df['Datum']
                <= pd.to_datetime(end_date_string)]

    return df


def collect_data_from_df(country, area, datatype, start_date_string, until=None, end_date_string=None):
    '''
    Collects data for a country `country` and a specific area `area` 
    either: new, recovered, fatality cases from df 

    `datatype` has to be one of `new`, `recovered`, `fatality`

    Returns np.array of shape (`max_days`, age_groups)
    '''
    if until and end_date_string:
        print('Can only specify `until` (days until end) or `end_date_string` (end date). ')
        exit(0)
    if end_date_string:
        max_days = (pd.to_datetime(end_date_string) -
                    pd.to_datetime(start_date_string)).days
    elif until:
        max_days = until

    else:
        raise ValueError('Need to pass either `until` or `end_date_string`')
   
    if country == 'GER':

        if datatype == 'new':
            ctr, indic = 'AnzahlFall', 'NeuerFall'
        elif datatype == 'recovered':
            ctr, indic = 'AnzahlGenesen', 'NeuGenesen'
        elif datatype == 'fatality':
            ctr, indic = 'AnzahlTodesfall', 'NeuerTodesfall'
        else:
            raise ValueError('Invalid datatype requested.')

        if area in command_line_area_codes['GER'].keys():
            landkreis = command_line_area_codes['GER'][area]
        else:
            raise ValueError('Invalid Landkreis requested.')

        df_tmp = get_preprocessed_data_germany(
            landkreis=landkreis, start_date_string=start_date_string, until=until, end_date_string=end_date_string)

        # check whether the new case counts, i.e. wasn't used in a different publication
        counts_as_new = np.array((df_tmp[indic] == 0) | (df_tmp[indic] == 1), dtype='int')

        df_tmp['new'] = counts_as_new * df_tmp[ctr]

        # count up each day and them make cumulative
        data = np.zeros((max_days, 6))  # value, agegroup
        for t in range(max_days):
            for agegroup in range(6):
                data[t, agegroup] += df_tmp[
                    (df_tmp.days <= t) & (df_tmp.age_group == agegroup)].new.sum()
                           
        return data.astype(int)

    elif country == 'CH':

        if datatype != 'new':
            return np.zeros([1, 9])
            # raise ValueError('Invalid datatype requested.')

        if area in command_line_area_codes['CH'].keys():
            canton = command_line_area_codes['CH'][area]
        else:
            raise ValueError('Invalid Canton requested.')

        df_tmp = get_preprocessed_data_switzerland(canton=canton, start_date_string=start_date_string, 
                                                   until=until, end_date_string=end_date_string)

        # count up each day and them make cumulative
        data = np.zeros((max_days, 9))  # value, agegroup
        for t in range(max_days):
            for agegroup in range(9):
                age_group_at_t = (df_tmp.days <= t) & (df_tmp.age_group == agegroup)
                data[t, agegroup] += df_tmp[age_group_at_t].new.sum()
            
        return data.astype(int)

    else:
        raise NotImplementedError('Invalid country requested.')

