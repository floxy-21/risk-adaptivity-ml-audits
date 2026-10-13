********** For 15-min Resolution HPD Alpha Version **************************

****************************************************************************
README FILE FOR HPD NETWORK 15-MINUTE OBSERVATIONS
Version 2.0 Alpha

This readme provides details on the alpha release of 15-minute observations
that are used to compute hourly precipitation totals in NCEI's Cooperative 
Observers Program (COOP) Hourly Precipitation Dataset (HPD).

These data are provided for the years 2014 through the present. They
continue the record of 15-minute observations that are available in NCEI's
DSI-3260 dataset (ending in December 2013). 

These data were collected from the COOP NWS Fischer-Porter network of gauges.
Details of the network and NCEI processing steps are provided in the 
Algorithm Theoretical Basis Document
(HPD-Auto-v1-ATBD-20170201.pdf) available on this ftp site.

--------------------------------------------------------------------------------
How to cite:

To acknowledge the specific version of the dataset used, please cite:
Hourly Precipitation Data (HPD) Network of 15-minute observatios, Version 2. 
[indicate sub-version number used following the decimal, e.g. Version 2.0] alpha,
NOAA National Centers for Environmental Information. [access date].

--------------------------------------------------------------------------------
NOTE:
The engineered accuracy of the Fischer-Porter network (F&P) gauges is one tenth
of an inch. However, the stations in the F&P network now measure precipitation to
one hundredth of an inch. The weighing gauge sensors are 
susceptible to noise at levels less than one tenth of an inch, but NCEI
believes a true precipitation signal can be identified at lighter amounts.
Although it can be challenging to always distinguish noise from the true
precipitation signal, NCEI has found that it can in general determine an
accurate precipitation amount at totals as low as one hundredth of an inch.
However, users are cautioned that there is less confidence in
precipitation amounts less than one tenth of an inch.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

I. DOWNLOAD QUICK START

Use either the comma separated value (csv) formatted files or 
the fixed format files (which are fixed record length).
The csv files are easiest to import into a spreadsheet such as Microsoft Excel and Google Sheets.
Fixed length formatted files are often easiest to use when writing a computer program.

Start by downloading "hpd-stations-inventory.csv" or "hpd-stations-inventory.txt," which have metadata for all stations.

Then download the following TAR file:

  - Either "hpd_all.15min.csv.tar.gz" or "hpd_all.15min.fixed_format.tar.gz"

Then uncompress and untar the contents of the tar file, 
e.g., by using the following Linux command:

tar xzvf hpd_all.15min.csv.tar.gz or tar xzvf hpd_all.15min.fixed_format.tar.gz

The files will be extracted into a subdirectory under the directory where the
command is issued.

ALTERNATIVELY, if you only need data for one station:

  - Find the station's name in either inventory file and note its station
    identification code (e.g., FLAGSTAFF, AZ is "USC00023009"); and
  - Download the data file (i.e., ".15m" file) that corresponds to this code 
    within either the /all_csv/ or /all_fixed_format/ subdirectory
    (e.g., "USC00023009.15m" has the data for FLAGSTAFF).  

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

II. CONTENTS OF ftp://ftp.ncdc.noaa.gov/pub/data/hpd/auto/v2/alpha/15min/

all_csv:                     Directory with ".15m.csv" comma separated value (csv) files for all stations
all_fixed_format:	     Directory with ".15m" fixed format files for all stations

hpd_all.15min.csv.tar.gz:    GZIP-compressed TAR file containing all csv formatted station files
hpd_all.15min.fixed_format.tar.gz:    GZIP-compressed TAR file containing all fixed format station files

hpd-stations-inventory.csv:  List of stations and their metadata (e.g., coordinates) in csv format
hpd-stations-inventory.txt:  List of stations and their metadata (e.g., coordinates) in fixed format

hpd-states.txt:              List of U.S. state codes used in hpd-stations-inventory.txt (and *.csv).

readme.15min.txt:            This file
status-15m.txt:              Notes on the current status of HPD 15-minute dataset

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

III. FORMAT OF COMMA SEPARATED VALUE (CSV) DATA FILES (".15m.csv" FILES)

Each ".15m.csv" station file contains precipitation totals taken every 15-minutes for one station. 
The name of the file corresponds to a station's identification code.
For example, "USC00313017.15m.csv" contains the data for the station with the identification code USC00313017.

Each record in a file contains one day of 15-minute data (96 observations).  
The variables on each line include the following with each variable separated by a comma (the fields are variable length):

These variables have the following definitions:

STNID      is the station identification code.  Please see 
           "hpd-stations-inventory.csv"
           for a complete list of stations and their metadata.

Lat        is latitude of the station (in decimal degrees).

Lon        is the longitude of the station (in decimal degrees).

Elev       is the elevation of the station (in meters, missing = -999.9).

YEAR-MO-DA is the year, month, and day of the record.

Element    is the element type.   Currently there is only one element type:
	   
           QPCP = 15-minute Precipitation total (hundreths of in) (Q stands for Quarter hour).
	   
0000Val    is the value on the first 15-minute observation of the day (i.e., the precipitation
           total during the time of day 00:00-00:15; missing = -9999).
           The units are hundredths of inch.

0000MF     is the measurement flag for the first 15-minute observation of the day. The possible
           values are:

	   This is a placeholder for measurement flags that will be added in a future beta release.

0000QF     is the quality flag for the first 15-minute observation of the day. The possible values
           are:

	   This is a placeholder for quality control flags that will be added in a future beta release.

0000S1     is the primary source flag for the first 15-minute observation of the day.
           The possible values are:

           Blank = No source (i.e., data value missing)
           4     = DSI-3240
           6     = DSI-3260 (not used in current version)
           H     = derived from digital data from the NWS HPD network

0000S2     is the secondary source flag for the 15-minute observation of the day.
           The possible values are:

           Blank = No source (i.e., no secondary source code applies)

           When data are available for the same time from more than one source,
           the highest priority source is chosen according to the following
           priority order (from highest to lowest):
           H,4,6


0015Val    is the value on the second 15-minute period of the day (i.e., time 00:15-00:30)

0015MF     is the measurement flag for the second 15-minute period of the day.

0015QF     is the quality flag for the second 15-minute period of the day.

0015S1     is the primary source flag for the second 15-minute period of the day.

0015S2     is the secondary source flag for the second 15-minute period of the day.

... and so on through the 96th 15-minute observation of the day (2345-0000) and its flags.

DlySum     is the sum of all the non-missing
           15-minute values in the day (i.e., daily sum).

DlySumMF   is the measurement flag placeholder that applies to the daily sum
           Currently this is always blank.

DlySumQF   is the quality flag for the daily sum. It is blank if all 96 15-minute
           values in the day were used to compute the sum,
           and set to "P" (for Partial daily sum) if fewer than all 96 15-minute
           values were used.

DlySumS1   is the primary source flag for the daily sum for consistency with the
           15-minute value primary source flag. Currently this is always blank.

DlySumS2   is the secondary source flag for the daily sum for consistency with
           the 15-minute value secondary source flag. It is always set to "C" to
           indicate the daily sum is Computed from the 15-minute values preceding
           it in the same daily data record ... as opposed to a daily sum that
           might be reported by an observer who examines a daily accumulation
           amount in a rain gauge.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

IV. FORMAT OF FIXED FORMAT DATA FILES (".15m" FILES)

As with the CSV files described above, each ".15m" file contains precipitation 
totals taken every 15-minutes for one station. 
The name of the file corresponds to a station's identification code.
For example, "USC00313017.15m" contains the data for the station with the identification code USC00313017.

Each record in a file contains one day of 15-minute data (96 observations).  
The variables on each line include the following: 
Note that unlike the .csv files, no comma is present in the fixed format files.

------------------------------
Variable   Columns   Type
------------------------------
ID            1-11   Character
YEAR         12-15   Integer
MONTH        16-17   Integer
DAY          18-19   Integer
ELEMENT      20-23   Character
0000Val      24-28   Integer
0000MF       29-29   Character
0000QF       30-30   Character
0000S1       31-31   Character
0000S2       32-32   Character
0015Val      33-37   Integer
0015MF       38-38   Character
0015QF       39-39   Character
0015S1       40-40   Character
0015S2       41-41   Character
  .           .          .
  .           .          .
  .           .          .
2345Val    879-883   Integer
2345MF     884-884   Character
2345QF     885-885   Character
2345S1     886-886   Character
2345S2     887-887   Character
------------------------------

The variables have the same definitions as those described in Section 3 above. (However, the fixed format
does not include daily sums.) 
Note that metadata information
Latitude, Longitude, and Elevation are not included in the fixed format file. Also the Year, Month, and Day
are separate elements in this file, while they were combined in the .csv file defined above.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

V. FORMAT OF "hpd-stations-inventory.csv"

The fields are variable length and delimited (separated) by commas.

The elements have the following definitions:

StnID      is the station identification code.  Note that the first two
           characters denote the FIPS  country code, the third character 
           is a network code that identifies the station numbering system 
           used, and the remaining eight characters contain the actual 
           station ID. 

           See "hpd-states.txt" for a list of state/territory codes.

           The network code  has the following two values:

           C = U.S. Cooperative Network identification number (last six 
               characters of the GHCN-Daily ID)
           W = WBAN identification number (last five characters of the 
               GHCN-Daily ID)

Lat        is latitude of the station (in decimal degrees).

Lon        is the longitude of the station (in decimal degrees).

Elev       is the elevation of the station (in meters, missing = -999.9).


State/Province is the U.S. postal code for the state (for U.S. stations only) or the US Territory.

Name       is the name of the station.

WMO_ID     is the World Meteorological Organization (WMO) number for the
           station.  If the station has no WMO number (or one has not yet 
	   been matched to this station), then the field is blank.

Sample_Interval    is in units of minute and indicates the typical
                            time between sampling of the level of water in
                            the gauge.

UTC_Offset         is the number of hours the station's local time
                            is offset from GMT. Negative values earlier than GMT.

POR_Date_Range	   is the first and last year-month-day of the station's Period of Record.

PCT_POR_Good	   is the percentage of non-missing and non-flagged observations 
                   during the station's POR.

Last_Half_POR	   is the first and last year-month-day of the last half of the station's POR.

PCT_Last_Half_Good is the percentage of non-missing and non-flagged observations during the 
                   last half of the station's POR.  

Last_Qtr_POR	   is the first and last year-month-day of the last 25% of the station's POR.

PCT_Last_Qtr_Good  is the percentage of non-missing and non-flagged observations during the 
                   last quater of the station's POR.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

VI. FORMAT OF "hpd-stations-inventory.txt"

---------------------------------------
Variable           Columns   Type
---------------------------------------
StnID                 1-11 Character
Lat                  13-20 Real
Lon                  22-30 Real
Elev                 32-37 Real
State/Province       39-40 Character
Name                42-122 Character
WMO_ID             124-128 Character
Sample_Interval    130-133 Character
UTC_Offset         135-139 Character
POR_Date_Range     141-157 Character
PCT_POR_Good       159-163 Real
Last_Half_POR      166-182 Character
PCT_Last_Half_Good 184-188 Real
Last_QTR_POR       191-207 Character
PCT_Last_Qtr_Good  209-213 Real
---------------------------------------

The elements have the same definitions as those provided in section V above.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

V. FORMAT OF "hpd-states.txt"

------------------------------
Variable   Columns   Type
------------------------------
CODE          1-2    Character
NAME         4-50    Character
------------------------------

These variables have the following definitions:

CODE       is the POSTAL code of the U.S. state/territory
           where the station is located 

NAME       is the name of the state or territory.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

VI.  REFERENCES

For additional information, please send an e-mail to hpd.ncdc@noaa.gov.
