README FILE FOR HOURLY PRECIPITATION DATA (HPD) NETWORK
Version 2.0

This dataset is available here:
https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/

This readme file (readme.csv.txt) is located in the doc/ subdirectory:
https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/doc/

The operational release of NCEI’s Hourly Precipitation Dataset (HPD),
known historically as DSI-3240 (NCDC 2003). The new dataset combines the legacy
data from DSI-3240 with a new source of data collected from the same
Fischer-Porter gauges, but which were upgraded to digital recording beginning
in the mid-2000s. As with the legacy DSI-3240 dataset, this new dataset provides
observations of hourly precipitation amounts from 1948 to the present.
Details are provided in the Algorithm Theoretical Basis Document
(CHPD-v2-ATBD-20181023.pdf) available on this ftp site.

--------------------------------------------------------------------------------
How to cite:

To acknowledge the specific version of the dataset used, please cite:
Hourly Precipitation Data (HPD) Network, Version 2. [indicate subset used
following decimal, e.g. Version 2.0],
NOAA National Centers for Environmental Information. [access date].

--------------------------------------------------------------------------------
NOTES:
The engineered accuracy of the Fischer-Porter network (F&P) gauges is one tenth
of an inch. However, the stations in the F&P network measure precipitation to
one hundredth of an inch. The weighing gauge sensors are
susceptible to noise at levels less than one tenth of an inch, but NCEI
believes a true precipitation signal can be identified at lighter amounts.
Although it can be challenging to always distinguish noise from the true
precipitation signal, NCEI feels that in most cases it can determine an
accurate precipitation amount at totals as low as one hundredth of an inch.
However, users are cautioned that there is less confidence in hourly
precipitation amounts less than one tenth of an inch.

Revision 02 ("r02" in archive file names) was released in October 2019.
The difference between Revisions 01 and 02 is that hourly precipitation totals
are no longer computed from the 15-min resolution digital data (primary source
flag = "H") when all four of the 15-min values are not available.  In Revision
01, an hourly total was computed and reported from any available 15-min data
within the hour.


--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

I. DOWNLOAD QUICK START

Start by downloading "HPD_v02r02_stationinv_cYYYYMMDD.csv", where cYYYYMMDD is
the creation date of the file, so each updated file will have a newer creation
date. This file has metadata for all HPD precipitation stations.

Then download the individual station data files desired from the
access/ subdirectory:
https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/access/

For each station desired:

  - Find the station's name in the metadata file
    (HPD_v02r02_stationinv_cYYYYMMDD.csv) and note its station
    identification code (e.g., FLAGSTAFF, AZ is "USC00023009"); and
  - Download the data file (i.e., ".csv" file) that corresponds to this code
    from the access/ subdirectory (e.g., "USC00023009.csv" has the data for
    FLAGSTAFF).

ALTERNATIVELY, if the entire network of nearly 2000 HPD stations is desired,
then you may download the most recent .tar.gz "archive file" containing all
station data files from the archive/ subdirectory:
https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/archive/

The archive file has the naming convention
HPD_v02r02_POR_sYYYYMMDD_eYYYYMMDD_cYYYYMMDD.tar.gz
... where sYYYYMMDD is the START date of the data contained in the file,
          eYYYYMMDD is the END   date of the data contained in the file, and
          cYYYYMMDD is CREATION date of the archive file

Then uncompress and untar the contents of the .tar.gz archive file,
e.g., by using the following Linux command:

tar xzvf HPD_v02r02_POR_sYYYYMMDD_eYYYYMMDD_cYYYYMMDD.tar.gz 

The station data files will be extracted into the directory where the tar
command is issued.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

II. CONTENTS OF https://www.ncei.noaa.gov/data/coop-hourly-precipitation/v2/

access:              Directory with ".csv" data files for all HPD stations

archive:             Directory containing the "archive files", 
                     i.e., a GZIP-compressed TAR file of all the station data
                     files found in the access/ directory, and a
                     GZIP-compressed version of the station inventory metadata
                     file found in the station-inventory/ directory.

doc:                 Directory containing all the documentation files related
                     to the HPD dataset, including::
                     - readme.csv.txt: This file
                     - hpd-states.txt: List of U.S. state/province codes used
                                       in HPD_v02r02_stationinv_cYYYYMMDD.csv
                     - status.txt:     Notes on the current status of HPD 

station-inventory:   Directory containing the latest metadata file,
                     HPD_v02r02_stationinv_cYYYYMMDD.csv

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

III. FORMAT OF station inventory metadata file:
     "HPD_v02r02_stationinv_cYYYYMMDD.csv"

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


State/Province is the U.S. postal code for the state (for U.S. stations only)
               or the US Territory.

Name       is the name of the station.

WMO_ID     is the World Meteorological Organization (WMO) number for the
           station.  If the station has no WMO number (or one has not yet
           been matched to this station), then the field is blank.

Sample_Interval    is in units of minute and indicates the typical time between
                   sampling of the level of water in the gauge.

UTC_Offset         is the number of hours the station's local time is offset
                   from GMT. Negative values are earlier than GMT.

POR_Date_Range     is the first and last year-month-day of the station's
                   Period Of Record (POR).

PCT_POR_Good       is the percentage of non-missing and non-flagged observations
                   during the station's POR.

Last_Half_POR      is the first and last year-month-day of the last half of the
                   station's POR.

PCT_Last_Half_Good is the percentage of non-missing and non-flagged observations
                   during the last half of the station's POR.

Last_Qtr_POR       is the first and last year-month-day of the last 25% of the
                   station's POR.

PCT_Last_Qtr_Good  is the percentage of non-missing and non-flagged observations
                   during the last quater of the station's POR.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

IV.  FORMAT OF HPD .csv DATA FILES:

Each ".csv" file contains data for one station. The name of the file corresponds
to a station's identification code.  For example, "USC00313017.csv" contains the
data for the station with the identification code USC00313017.

Each record in a file contains one day of hourly data.  The variables on each
line include the following:


StnID      is the station identification code.  Please see 
           "hpd-stations-inventory.txt"
           for a complete list of stations and their metadata.

Lat        is latitude of the station (in decimal degrees).

Lon        is the longitude of the station (in decimal degrees).

Elev       is the elevation of the station (in meters, missing = -999.9).

Year       is the year of the data record.

Month      is the month of the data record.

Day        is the day of the data record (i.e., the day of month).

Element    is the element type.   Currently there is only one element type:
	   
           HPCP = Hourly Precipitation total (hundredths of in)
	   
		   
HR00Val    is the value on the first hour of the day (i.e., the precipitation
           total during the time of day 00:00-01:00; missing = -9999).
           The units are hundredths of inch.

HR00MF     is the measurement flag for the first hour of the day. The possible
           values are:

           Blank = no measurement information applicable
           g     = a carry-over measurement flag from the DSI-3240 dataset
                   which was used only on the very first hour of the month
                   if there was zero precipitation during that hour. The purpose
                   of this flag was mainly to indicate that the station was
                   functional and reporting during the month. Normally in
                   DSI-3240, zero precipitation amounts were not included in the
                   data file in order to save space. This HPD dataset does
                   include zero precipitation totals, both those assumed from
                   the DSI-3240 dataset and those determined from the digital
                   recordings of bucket level data. 
           Z     = represents an "assumed" zero precipitation total. Usually
                   these are values from the DSI-3240 dataset. The rule in that
                   dataset was to "assume" a zero total for any hour where
                   nothing else was reported or indicated for that hour as long
                   as the very first hour of the month had a non-zero amount or
                   a zero amount with the "g" measurement flag. Zero amounts
                   were omitted from the DSI-3240 dataset in order to save disk
                   space. We are not concerned with that anymore.
	   a     = represents the beginning hour of an accumulation period.
                   Sometimes multi-hour accumulations were reported in DSI-3240,
                   so they were brought over for the period of record in which
                   we have DSI-3240 data when that was the best information
                   available. The data value for the beginning of an
                   accumulation period is set to missing (-9999).
	   .     = represents an hour during an accumulation period, between the
                   beginning and ending hours of the accumulation period.
                   The data value during the midst of an accumulation period is
                   set to missing (-9999). Accumulations across multiple hours
                   exist only from the legacy DSI-3240 data source. 
	   A     = designates the end of an accumulation period.
                   The accumulation total for the period is given for the
                   data value.
           T     = trace of precipitation

HR00QF     is the quality flag for the first hour of the day.
           The possible values are:

           Blank = did not fail any quality assurance check
           X     = failed global extreme exceedence check
           N     = failed negative precipitation check
           Y     = failed state extreme exceedence check
                   (performed on daily totals)
           K     = failed streak/frequent-value check
           G     = failed gap check
           O     = failed climatological outlier check
           Z     = flagged as a result of an official Datzilla investigation
	   A     = The value is not an hourly precipitation total but rather
                   an accumulation total for a period greater than an hour in
                   duration and lasting through the end of this hour.
                   (See measurement flags "a" and "." for the beginning time of
                   the accumulation period and times during the accumulation
                   period, respectively.) Accumulations across multiple hours
                   exist only from the legacy DSI-3240 data source.
           M     = represents the associated value at this observation time is
                   missing in the DSI-3240 dataset and no alternate data source
                   is available. This is a carry-over indicator from DSI-3240 to
                   allow the user to distinguish between missing and deleted
                   data in that older system. (See the "D" quality flag.)
                   However, the most consistent way to identify hours of missing
                   data across the entire dataset is to test if the
                   precipitation value is equal to the special missing value
                   of -9999. 
           D     = represents the associated value at this time was deleted by
                   the DSI-3240 processing system. Usually this was done
                   manually by a trained meteorological technician who made the
                   decision using ancillary information and experience.
           Q     = a carry-over quality flag the legacy DSI-3240 data source. 
                   Prior to 1996: Indicates value failed an extreme value test
                   (value will be present); data are to be used with caution.
                   Extremes tests were:
                   1) If the value was not an accumulated precipitation total,
                      the value failed the one-hour statewide 100-year return
                      period precipitation.
                   2) If the value was an accumulated precipitation total,
                      the value failed the 24-hour statewide extreme
                      precipitation total. This flag was assigned during a 1997
                      NCDC rehabilitation of the 1900-1995 DSI-3240 archive.
                   Since January 1996: A single erroneous datum (value will be
                   present). Lowest data resolution is hourly. This flag is
                   rarely used in DSI-3240 since 1996.
           q     = a carry-over quality flag the legacy DSI-3240 data source. 
                   Used since January 1996. An hourly value excludes one or
                   more 15 minute periods. Lowest data resolution is 15 minutes.
           R     = a carry-over quality flag the legacy DSI-3240 data source.
                   Used since January 1996. Indicates data values are suspect
                   with regard to the times or period of occurrence. 


HR00S1     is the primary source flag for the first hour of the day.
           The possible values are:

           Blank = No source (i.e., data value missing)
           4     = DSI-3240
           6     = DSI-3260 (not used in current version)
           H     = derived from digital data from the NWS HPD network

HR00S2     is the secondary source flag for the first hour of the day.
           The possible values are:

           Blank = No source (i.e., no secondary source code applies)
           C     = hourly total is computed from high-temporal resolution
                   totals (e.g., computed from 15-min precip totals)

	   
	   When data are available for the same time from more than one source,
	   the highest priority source is chosen according to the following
	   priority order (from highest to lowest):
           H,4,6

	   
HR01Val    is the value on the second hour of the day (i.e., time 01:00-02:00)

HR01MF     is the measurement flag for the second hour of the day.

HR01QF     is the quality flag for the second hour of the day.

HR01S1     is the primary source flag for the second hour of the day.

HR01S2     is the secondary source flag for the second hour of the day.

... and so on through the 24th hour of the day.

DlySum     is the sum of all the non-missing, non-quality-control-flagged
           hourly values in the day (i.e., daily sum).

DlySumMF   is the measurement flag placeholder that applies to the daily sum
           for consistency with the hourly value measurement flag.
           Currently this is always blank.

DlySumQF   is the quality flag for the daily sum. It is blank if all 24 hourly
           values in the day were used to compute the sum,i
           and set to "P" (for Partial daily sum) if fewer than all 24 hourly
           values were used.

DlySumS1   is the primary source flag for the daily sum for consistency with the
           hourly value primary source flag. Currently this is always blank.

DlySumS2   is the secondary source flag for the daily sum for consistency with
           the hourly value secondary source flag. It is always set to "C" to
           indicate the daily sum is Computed from the hourly values preceding
	   it in the same daily data record ... as opposed to a daily sum that
           might be reported by an observer who examines a daily accumulation
           amount in a rain gauge. 

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

