import os, sys
import pandas as pd


# Set current working directory to script location
working_dir = r'C:\Users\bnichols\travel-studies\2017\daysim_conversions'
os.chdir(working_dir)

# Import local module variables
from lookup import *

# Set input paths
person_file_dir = r'J:\Projects\Surveys\HHTravel\Survey2017\Data\Export\Version 2\Restricted\In-house\2017-internal-v2-R-2-person.xlsx'
trip_file_dir = r'\\aws-prod-file01\datateam\Projects\Surveys\HHTravel\Survey2017\Data\Export\Version 3\Restricted\In-house\2017-internal-v3-R-5-trip.xlsx'
#trip_file_dir = r'R:\e2projects_two\SoundCastDocuments\2017Estimation\trip_from_db.csv'
purp_lookup_dir = r'R:\e2projects_two\SoundCastDocuments\2017Estimation\purp_lookup.csv'

# Output directory
#output_dir = r'C:\Users\bnichols\travel-studies\2017\daysim_conversions'
output_dir = r'R:\e2projects_two\SoundCastDocuments\2017Estimation'


def process_person_file(person_file_dir):
    """ Create Daysim-formatted person file from Survey Excel file. """

    # FIXME: use final version from Elmer

    person = pd.read_excel(person_file_dir, skiprows=1)

    # Full time worker
    person.loc[person['employment'] == 1, 'pptyp'] = 1

    # Part-time worker
    person.loc[person['employment'] == 2, 'pptyp'] = 2

    # Non-working adult age 65+
    person.loc[(person['employment'] != 1) &  (person['age'].isin([10,11,12])), 'pptyp'] = 3

    # High school student age 16+
    person.loc[(person['age'] >= 4) & (person['schooltype'].isin([3,4,5])), 'pptyp'] = 6

    # university student (full-time)
    person.loc[(person['schooltype'].isin([6,7])) & (person['student'] == 3), 'pptyp'] = 5

    # Child age 5-15
    person.loc[person['schooltype'].isin([2,3]), 'pptyp'] = 7

    # child under 5
    person.loc[person['schooltype'].isin([1]), 'pptyp'] = 8

    # Non-working adult age 65 should accoutn for all others
    person.loc[person['pptyp'].isnull(), 'pptyp'] = 4

    # Person worker type
    person.loc[person['employment'].isin([1]), 'pwtyp'] = 1
    person.loc[person['employment'].isin([2]), 'pwtyp'] = 2
    person.loc[person['employment'].isin([3,4,5,6,7]), 'pwtyp'] = 0
    person['pwtyp'].fillna(0,inplace=True)
    person['pwtyp'] = person['pwtyp'].astype('int')

    # Transit pass availability
    person['ptpass'] = 0
    person.loc[(person['tran_pass_12'].isin([1,2])) | (person['benefits_3'].isin([2,3])),'ptpass'] = 1

    # Paid parking at work (any level of subsidy counts as 'paid')
    person['ppaidprk'] = 0
    person.loc[person['workpass'].isin([3,4]), 'ppaidprk'] = 1

    # Map other variables from lookup tables
    person['age'] = person['age'].astype('int')
    person['pagey'] = person['age'].map(age_map)
    person['pgend'] = person['gender'].map(gender_map)
    person['pstyp'] = person['student'].map(pstyp_map)
    person['pstyp'].fillna(0,inplace=True)
    person['hhno'] = person['hhid']
    person['pno'] = person['pernum']
    person['psexpfac'] = person['hh_wt_revised']
    person['pwtaz'] = -1
    person['pstaz'] = -1
    person['pwpcl'] = -1
    person['pspcl'] = -1

    daysim_cols = ['hhno', 'pno', 'pptyp', 'pagey', 'pgend', 'pwtyp', 'pwpcl', 'pwtaz', 'pwautime',
               'pwaudist', 'pstyp', 'pspcl', 'pstaz', 'psautime', 'psaudist', 'puwmode', 'puwarrp', 
               'puwdepp', 'ptpass', 'ppaidprk', 'pdiary', 'pproxy', 'psexpfac']

    # Add empty columns to fill in later with skims
    for col in daysim_cols:
        if col not in person.columns:
            person[col] = -1
        
    person = person[daysim_cols]

    return person

def process_trip_file(trip_file_dir, purp_lookup_dir, person):
    """ Convert trip records to Daysim format."""

    #trip = pd.read_csv(trip_file_dir)
    trip = pd.read_excel(trip_file_dir, sheetname='5-Trip', skiprows=1)
    df_purp_lookup = pd.read_csv(purp_lookup_dir)
    trip['hhno'] = trip['hhid']
    trip['pno'] = trip['pernum']
    trip['day'] = trip['daynum'].astype(int)
    trip['tsvid'] = trip['recid']

    # Select only weekday trips (Should we also include Friday?)
    #trip = trip[trip['dayofweek'].isin([1,2,3,7])]    # This is messed up in the current version of survey
    # use nwkdays > 0 instead
    trip = trip[trip['nwkdays'] > 0]

    # FIXME
    # Filter out people that have some missing information, like trip purpose
    # Don't just filter out trips for some applications? 

    # Survey DB is formatted with string values, need to translate again with above dict
    #df_purp_lookup = pd.read_sql(sql='select * from HHSurvey.DataExplorerValues2017 where VariableID = 125', con=conn)
    new_purp_map = {}
    for val in df_purp_lookup['ValueOrder'].unique():
        text = df_purp_lookup.loc[df_purp_lookup['ValueOrder'] == val,'ValueText'].values[0]
        new_purp_map[text] = purpose_map[val]

    # FIXME: this field is whack
    trip['day'] = trip['dayofweek']

    trip['opurp'] = trip['origin_purpose'].map(purpose_map)
    trip['dpurp'] = trip['dest_purpose'].map(purpose_map)

    trip['dorp'] = trip['driver'].map(dorp_map)
    # Dorp of N/A is e in daysim, fillna with this value
    trip['dorp'] = trip['dorp'].fillna(3)

    # origin and destination TAZs
    trip['otaz'] = trip['o_taz2010']
    trip['dtaz'] = trip['d_taz2010']
    trip['otaz'] = trip['otaz'].fillna(-1)
    trip['dtaz'] = trip['dtaz'].fillna(-1)


    ##############################
    # Start and end time
    ##############################
    # Filter out rows with None
    trip = trip[-trip['depart_time_hhmm'].isnull()]
    trip = trip[-trip['arrival_time_hhmm'].isnull()]

    # Minutes
    for db_col_name, daysim_col_name in {'arrival_time_hhmm': 'arrtm', 'depart_time_hhmm': 'deptm'}.items():

        # Filter rows without valid depart and start times
        trip = trip[-trip[db_col_name].isnull()]
    
        # Get minutes from time stamp, as values to right of :
        minutes = trip[db_col_name].apply(lambda row: str(row).split(' ')[-1].split(':')[1])
        minutes = minutes.apply(lambda row: row.split('.')[0]).astype('int') # Trim any decimal places and takes whole numbers
    
        # Get hours from time stamp
        hours = trip[db_col_name].apply(lambda row: str(row).split(' ')[-1].split(':')[0]).astype('int')
    
        # In minutes after midnight****
        ##########
        # NOTE: Check that daysim uses MAM and not minutes after 3 A
        ##########
        trip[daysim_col_name] = hours*60 + minutes
    
    ##############################
    # Mode
    ##############################
    trip['mode'] = 'Other'

    # Get HOV2/HOV3 based on total number of travelers
    auto_mode_list = [3,4,5,6,7,8,9,10,11,12,16,17,18,21,22,33,34]
    trip.loc[(trip['travelers_total'] == 1) & (trip['mode_1'].isin(auto_mode_list)),'mode'] = 'SOV'
    trip.loc[(trip['travelers_total'] == 2) & (trip['mode_1'].isin(auto_mode_list)),'mode'] = 'HOV2'
    trip.loc[(trip['travelers_total'] > 2) & (trip['mode_1'].isin(auto_mode_list)),'mode'] = 'HOV3+'
    # transit
    trip.loc[trip['mode_1'].isin([23,32,41,42,52]),'mode'] = 'Transit'
    trip.loc[trip['mode_1'].isin([1]),'mode'] = 'Walk'
    trip.loc[trip['mode_1'].isin([2]),'mode'] = 'Bike'
    trip.loc[trip['mode_1'].isin([37]),'mode'] = 'TNC' # Should this also include traditonal Taxi?
    trip['mode'] = trip['mode'].map(mode_dict)
    trip['trexpfac'] = trip['trip_weight_revised']

    ##############################
    # Origin and Destination Types
    ##############################

    # Assume "other" by default
    trip.loc[:,'oadtyp'] = 4
    trip.loc[:,'dadtyp'] = 4

    # Trips with origin/destination purpose of "Home" (0) have a origin/destination address type of "Home" (1)
    trip.loc[trip['opurp'] == 0,'oadtyp'] = 1
    trip.loc[trip['dpurp'] == 0,'dadtyp'] = 1

    # Trips to/from work are considered "usual workplace" only if dpcl == workplace parcel
    #### FIX ME: do not have PARCELS, only using TAZ
    # must join person records to get usual work and school location
    trip = trip.merge(person[['hhno','pno','pwtaz','pstaz']], on=['hhno','pno'], how='left')

    # If trip is to/from TAZ of usual workplace and trip purpose is work
    trip.loc[(trip['opurp'] == 0) & (trip['otaz'] == trip['pwtaz']),'oadtyp'] = 2
    trip.loc[(trip['dpurp'] == 0) & (trip['dtaz'] == trip['pwtaz']),'dadtyp'] = 2

    # usual school
    trip.loc[(trip['opurp'] == 0) & (trip['otaz'] == trip['pstaz']),'oadtyp'] = 3
    trip.loc[(trip['dpurp'] == 0) & (trip['dtaz'] == trip['pstaz']),'dadtyp'] = 3

    # Change mode
    trip.loc[trip['opurp'] == 10,'oadtyp'] = 6
    trip.loc[trip['dpurp'] == 10,'dadtyp'] = 6

    ##############################
    # Set Skim Values
    ##############################

    trip['travcost'] = -1
    trip['travtime'] = -1
    trip['travdist'] = -1

    # Add submode
    trip['pathtype'] = 1
    for index, row in trip.iterrows():
        if [23 or 32 or 41 or 42 or 52] in list(row[['mode_1','mode_2','mode_3','mode_4']].values):
            # ferry or water taxi
            if 32 in row[['mode_1','mode_2','mode_3','mode_4']].values:
                trip.loc[index,'pathtype'] = 7
            # commuter rail
            elif 41 in row[['mode_1','mode_2','mode_3','mode_4']].values:
                trip.loc[index,'pathtype'] = 6
            # 'Urban rail (e.g., Link light rail, monorail)'
            elif [42 or 52] in row[['mode_1','mode_2','mode_3','mode_4']].values:
                trip.loc[index,'pathtype'] = 4
            else:
                trip.loc[index,'pathtype'] = 3
        
    trip['opcl'] = -1
    trip['dpcl'] = -1
    trip_cols = ['hhno','pno','tsvid','day','mode','opurp','dpurp','deptm',
            'otaz','dtaz','opcl','dpcl','oadtyp','dadtyp',
            'arrtm','trexpfac','travcost','travtime','travdist',
        'pathtype']

    trip = trip[-trip['mode'].isnull()]
    trip = trip[-trip['opurp'].isnull()]
    trip = trip[-trip['dpurp'].isnull()]
    trip = trip[-trip['otaz'].isnull()]
    trip = trip[-trip['dtaz'].isnull()]

    # Write to file
    trip = trip[trip_cols]

    return trip

def build_tour_file(trip):
    """ Generate tours from Daysim-formatted trip records. """

    trip['personid'] = trip['hhno'].astype('int') + trip['pno'].astype('int')

    tour_dict = {}
    mylist = []
    bad_trips = []
    tour_id = 0

    for personid in trip['pno'].value_counts().index.values:
    #for personid in [1713260904]:

        person_df = trip.loc[trip['pno'] == personid]
        # Loop through each day
        for day in person_df['day'].unique():
            df = person_df.loc[person_df['day'] == day]
    
            # First trip record should be home (?)
            if df.groupby('personid').first()['opurp'].values[0] != 0:
                bad_trips.append(df['personid'].iloc[0])
                continue

            # identify home-based tours 
            home_tours_start = df[df['opurp'] == 0]
            home_tours_end = df[df['dpurp'] == 0]

            # skip person if they have a different number of tour starts/ends at home
            if len(home_tours_start) != len(home_tours_end):
                bad_trips.append(df['personid'].iloc[0])
                continue

            # Loop through each set of home-based tours
            for set_index in range(len(home_tours_start)):

                tour_dict[tour_id] = {}       

                # start row for this set
                start_row_id = home_tours_start.index[set_index]
        #         print start_row
                end_row_id = home_tours_end.index[set_index]
        #         print '-----'
                # iterate between the start row id and the end row id to build the tour

                # Select slice of trips that correspond to a trip set
                _df = df.loc[start_row_id:end_row_id]

                #################################
                # Skip this trip set under certain conditions
                #################################

                if len(_df) == 0:
                    continue

                # Trips with negative purposes
                if (_df['opurp'] < 0).any() or (_df['dpurp'] < 0).any():
                    print('negative person :(' + str(_df['personid'].iloc[0]))
                    bad_trips.append(df['personid'].iloc[0])
                    continue

                # Trips with same opurp and dpurp that is home
                if len(_df[(_df['opurp'] == _df['dpurp']) & (_df['opurp'] == 0)]) > 0:
                    bad_trips.append(df['personid'].iloc[0])
                    continue

        #         # Trips that have different purposes in sequence
        #         if len (df[df.shift(-1)['opurp']!=df['dpurp']]) > 0:
        #             bad_trips.append(df['personid'].iloc[0])
        #             continue

                # First row contains origin information
                tour_dict[tour_id]['tlvorig'] = _df.iloc[0]['deptm']
                tour_dict[tour_id]['tardest'] = _df.iloc[0]['arrtm']
                tour_dict[tour_id]['totaz'] = _df.iloc[0]['otaz']
                tour_dict[tour_id]['topcl'] = _df.iloc[0]['opcl']
                tour_dict[tour_id]['toadtyp'] = _df.iloc[0]['oadtyp']
                # NEED PARCEL DATA ON TRIP RECORDS!!!

                # Last row contains arrival time at destination
                #### FIX ME: this should be the departure 
                tour_dict[tour_id]['tlvdest'] = _df.iloc[-1]['deptm']
                tour_dict[tour_id]['tarorig'] = _df.iloc[-1]['arrtm']

                # Household and person info
                tour_dict[tour_id]['hhno'] = _df.iloc[0]['hhno']
                tour_dict[tour_id]['pno'] = _df.iloc[0]['pno']
                tour_dict[tour_id]['day'] = day

                # Identify primary purpose and figure out the tour halves
            #   ****ASSUMING primary tour is the activity that takes the longest amount of time

                 # Determine if this is part of the first half tour or second half tour
                # calculate duration, as difference between arrival at a place and start of next trip
                _df['duration'] = _df.shift(-1).iloc[:-1]['deptm']-_df.iloc[:-1]['arrtm']

                if len(_df) > 3:
                    mylist.append(_df['personid'].iloc[0])

                # For tour groups with only 2 trips, the halves are simply the first and second trips
                if len(_df) == 2:
                    tour_dict[tour_id]['pdpurp'] = _df.iloc[0]['dpurp']
                    tour_dict[tour_id]['tripsh1'] = 1
                    tour_dict[tour_id]['tripsh2'] = 1
                    tour_dict[tour_id]['tdadtyp'] =  _df.iloc[0]['dadtyp']
                    tour_dict[tour_id]['odadtyp'] =  _df.iloc[0]['oadtyp']
                    tour_dict[tour_id]['tpathtp'] = _df.iloc[0]['pathtype']

                # For tour groups with > 2 trips, calculate primary purpose and halves
                else:
                    # Assuming that the primary purpose is the purpose for the trip to place with longest duration
                    # Exclude trips witho only change-mode (10) to find primary purpose
                    primary_purp_index = _df[_df['dpurp'] != 10]['duration'].idxmax()
                    tour_dict[tour_id]['pdpurp'] = _df.loc[primary_purp_index]['dpurp']
                

                    # Get the tour DTAZ as the DTAZ of the primary trip destination; also dest address type
                    tour_dict[tour_id]['tdtaz'] = _df.loc[primary_purp_index]['dtaz']
                    tour_dict[tour_id]['tdpcl'] = _df.loc[primary_purp_index]['dpcl']
                    tour_dict[tour_id]['tdadtyp'] = _df.loc[primary_purp_index]['dadtyp']
                
                    # Pathtype is defined by a heirarchy, where highest number is chosen first
                    # Ferry > Commuter rail > Light Rail > Bus > Auto Network
                    tour_dict[tour_id]['tpathtp'] = _df.loc[_df['mode'].idxmax()]['pathtype']
                
                    # need destination parcel
                
                    #### Note that this probably needs to change
                    #### do we count stops separately than subtours?

                    # Get number of trips in the first half tour
                    tour_dict[tour_id]['tripsh1'] = len(_df.loc[0:primary_purp_index])

                    # trips in second half tour
                    tour_dict[tour_id]['tripsh2'] = len(_df.loc[primary_purp_index+1:])

                    # look for subtours
                    ##### FIX ME: #####
                    # for now just set subtours as 0 - do not use this for tour estimation



                # Calculate number of subtours
                # trips that have the same origin/dest pairs before returning home

        #         print personid

                # Extract main mode type
                # use a heirarchy of modes used on the trip
                mode_list = _df['mode'].value_counts().index.astype('int').values
                mode_heirarchy = [3,4,5,6,9,2,1]
                for mode in mode_heirarchy:
                    if mode in mode_list:
                        tour_dict[tour_id]['tmodetp'] = mode
                        break

                # Identify work-based subtours
                # Subtours require:
                # - at least 2 trips in addition to initial and final trips
                # - work purpose

                if (len(_df) >= 4) & (tour_dict[tour_id]['pdpurp'] == 1):
    #                 my_df = _df.copy()
    #                 # Considered a subtour if the middle trips start and end from work
    #                 subtour_ends = len(_df[(_df['opurp'] == 1) & (_df['dpurp'] != 0)]) + len(_df[(_df['opurp'] != 0) & (_df['dpurp'] == 1)])
    #                 subtours = subtour_ends/2

                    subtour_index_start_values = _df[(_df['opurp'] == 1) & (-_df['dpurp'].isin([0,1]))].index.values    
                    local_index = 0
                    subtours = 0
                    for i in subtour_index_start_values:
        #                 print(i)
                        # Loop through next rows until a return trip to work is found
                        # unless it hits the next subtour_index_start_value

                        while local_index < len(subtour_index_start_values):
                            if (_df.loc[i+1]['dpurp'] == 1) & ((_df.loc[i+1]['opurp'] != 0) or (_df.loc[i+1]['opurp'] != 1)):
                                # Found the end of the subtours
                                subtours += 1
    #                         print(local_index)
                            local_index += 1
                else:
                    subtours = 0
                tour_dict[tour_id]['subtrs'] = subtours
                
                tour_id += 1
            
    tour = pd.DataFrame.from_dict(tour_dict, orient='index')    

    for col in ['jtindex', 'parent', 
                'tautotime', 'tautocost', 'tautodist', 
                'phtindx1', 'phtindx2', 'fhtindx1', 'fhtindx2']:
        tour[col] = -1

    tour['toexpfac'] = 1

    return tour


def main():
    person = process_person_file(person_file_dir)
    trip = process_trip_file(trip_file_dir, purp_lookup_dir, person)
    tour = build_tour_file(trip)

    # Write files
    for df_name, df in {'person': person, 'trip': trip, 'tour': tour}.items():
        df.to_csv(os.path.join(output_dir,df_name+'17.csv'), index=False)

if __name__ == '__main__':
    main()