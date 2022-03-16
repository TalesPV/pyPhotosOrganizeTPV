# Basic references:
# https://www.youtube.com/watch?v=--_K4G3HCcI
# https://blog.gunderson.tech/26307/using-virtual-environment-requirements-txt-with-python
# https://www.programiz.com/python-programming/datetime/strftime
# Other references:
# Reference: https://www.geeksforgeeks.org/working-images-python/
# Reference:  https://www.codevscolor.com/python-print-date-time-hour-minute
# Reference: https://www.programiz.com/python-programming/datetime
# Reference: https://www.tutorialspoint.com/How-to-print-current-date-and-time-using-Python
# Reference: https://pypi.org/project/coloredlogs/
# Reference: https://coloredlogs.readthedocs.io/en/latest/readme.html
# Reference: https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
# Reference: https://www.geeksforgeeks.org/logging-in-python/

from array import ArrayType
import os
import platform
import re
import sys
import pathlib
import datetime
import time
import shutil
import logging
import piexif
import argparse
#import exifread

from xmlrpc.client import Boolean, DateTime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from asyncio import exceptions
from pickle import FALSE
#from GPSPhoto import gpsphoto

# Configuire Colored Logs:

import coloredlogs

# Obtain parameters from the system call:

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-f', '--folders', type=str, required=False, default='%Y_%m')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')
parser.add_argument('-w', '--overwrite', type=str, required=False, default='d')
parser.add_argument('-q', '--batch_quantity_files', type=int, required=False, default=0)
parser.add_argument('-y', '--exif_min_year_discart_date', type=int, required=False, default=1980)
parser.add_argument('-s', '--min_size_escape_low_resolution', type=int, required=False, default=200000)
parser.add_argument('-g', '--generate_folder_sufix', type=bool, required=False, default=True)
parser.add_argument('-n', '--rename_file', type=bool, required=False, default=True)
parser.add_argument('-l', '--timestamp_log', type=bool, required=False, default=True)

args = parser.parse_args()

# Version:
PROJECT_VERSION = '1.0.0.20220315000400'
PROJECT_DOING = 'Getting GPS information.'

# Define extensions to be processed and to obtain metadata:
IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.gif', '.bmp', '.tif')
VIDEO_EXTENSIONS = ('.mov', '.mp4', '.avi', '.mov')
MSOFFICE_EXTENSIONS = ('.doc', '.docx', '.xls', '.xlsx')
OTHER_EXTENSIONS = ('.pdf', )
ALL_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + MSOFFICE_EXTENSIONS + OTHER_EXTENSIONS


#----------------------------------------------------------------------#
# Reference: https://stackoverflow.com/questions/2909975/python-list-directory-subdirectory-and-files#2909998
def tpv_move_file(file_name_absolut: str = '', new_absolut_file_name: str = '', overwrite_option: str = 'd', logger: logging.Logger = None) -> tuple:
	original_file_size:int = 0
	destination_file_size:int = 0
	rindex_dot: int = 0
	file_name_counter: int = 0
	now: datetime = None
	sufix_dup_file: str = ''
	new_absolut_file_name_used: str = ''
	invalid_name: bool = True
	file_was_on_destiny:bool = False

	# TODO: Criar um real_action que inicia com o overwrite_option e depende da situação do arquivo

	new_absolut_file_name_used = new_absolut_file_name
	if os.path.exists(new_absolut_file_name):
		file_was_on_destiny = True
		if (logger is not None):
			logger.warning('File exist on destination!')
			logger.warning('Original:')
			logger.warning(file_name_absolut)
			logger.warning('Destination:')
			logger.warning(new_absolut_file_name)
		try:
			original_file_size = os.path.getsize(file_name_absolut)
			destination_file_size = os.path.getsize(new_absolut_file_name)
		except Exception as e:
			if (logger is not None):
				logger.error('Error 20220315023600 obtain files size: {err_msg}'.format(err_msg=e))
			else:
				raise e

		if (logger is not None):
			logger.debug('Tamanho origem: ' + str(original_file_size))
			logger.debug('Tamanho destino: ' + str(destination_file_size))

		if (overwrite_option == 'i'):
			new_absolut_file_name_used = ''
			# Ignoring duplicate files (keep original and destination it was existing):
			if (logger is not None):
				logger.info('Ignoring file!')
		else:
			new_absolut_file_name_used = new_absolut_file_name
			if ((overwrite_option == 'd') or (original_file_size != destination_file_size)):
				# Duplicate option or files with differente size:
				invalid_name = True
				file_name_counter = 100
				while (invalid_name):
					now = datetime.datetime.now()
					sufix_dup_file = now.strftime('%Y%m%d%H%M%S{file_name_counter}'.format(file_name_counter = file_name_counter))
					rindex_dot = new_absolut_file_name.rindex('.')
					new_absolut_file_name_used = new_absolut_file_name[0:rindex_dot] + '-' + sufix_dup_file + new_absolut_file_name[rindex_dot:]
					invalid_name = os.path.exists(new_absolut_file_name_used)
					if (not invalid_name):
						if (logger is not None):
							logger.warning('New file name to duplicate:')
							logger.warning(new_absolut_file_name_used)
					else:
						file_name_counter = file_name_counter + 1

	if ((not(file_was_on_destiny)) or (overwrite_option != 'i')):
		# Overwriting or Duplicating:
		try:
			shutil.move(file_name_absolut, new_absolut_file_name_used)
			#os.rename(file_name_absolut, new_absolut_file_name_used)
			#os.link(file_name_absolut, new_absolut_file_name_used)
			#os.unlink(file_name_absolut)
		except Exception as e:
			if (logger is not None):
				logger.error('Error 20200315030200 moving file do destination: {err_msg}'.format(err_msg=e))
			else:
				raise e

	del(original_file_size)
	del(destination_file_size)
	del(rindex_dot)
	del(file_name_counter)
	del(now)
	del(sufix_dup_file)
	del(invalid_name)
	return(file_was_on_destiny, new_absolut_file_name_used)

#----------------------------------------------------------------------#
# Reading Geodata information:
# Reference: https://towardsdatascience.com/grabbing-geodata-from-your-photos-library-using-python-60eb0462e147
# Reference: https://sylvaindurand.org/gps-data-from-photos-with-python/
# Reference: https://pypi.org/project/gpsphoto/
# Reference: https://medium.com/spatial-data-science/how-to-extract-gps-coordinates-from-images-in-python-e66e542af354
# Reference: https://stackoverflow.com/questions/19804768/interpreting-gps-info-of-exif-data-from-photo-in-python
def get_geodata_exif(absolut_file_name: str = '', logger: logging.Logger = None) -> str:

	#TODO: GEOTAG!

	'''
	o_latitude: float = 0.00
	o_longitude: float = 0.00
	latitude: int = 0
	longitude: int = 0

	try:
		image = Image.open(file_name_absolut)
		exif_dict = piexif.load(image.info['exif'])
	except Exception as e:
		if (logger is not None):
			logger.error("Error 20220313062100 to get metadata EXIF: {msg_e}".format(msg_e=e))
		else:
			raise e
	if (len(exif_dict["Exif"]) > 0):
		exif = image._getexif()
		with open(file_name_absolut, 'rb') as f:
			tags = exifread.process_file(f)
			latitude = tags.get('GPS GPSLatitude')
			latitude_ref = tags.get('GPS GPSLatitudeRef')
			longitude = tags.get('GPS GPSLongitude')
			longitude_ref = tags.get('GPS GPSLongitudeRef')
			print('latitude {lat_value}, and longitude {lon_value}'.format(lat_value = latitude_ref, lon_value = longitude_ref))
	'''
	return('')

#----------------------------------------------------------------------------------------------#
# Reference: https://pypi.org/project/coloredlogs/
def log_inicialization(log_with_timestamp: Boolean = False) -> logging.Logger:

	log_file_name: str = ''
	logger: logging.Logger = None

	if (platform.system() == 'Windows'):
		if (log_with_timestamp):
			log_file_name='.\\tmp\\' + datetime.datetime.strftime(datetime.datetime.now(), '%Y_%m_%d_%Hh%Mm%Ss') + '-py_photos_organize_tpv.log'
		else:
			log_file_name='.\\tmp\\py_photos_organize_tpv.log'
	else:
		if (log_with_timestamp):
			log_file_name='.//tmp//' + datetime.datetime.strftime(datetime.datetime.now(), '%Y_%m_%d_%Hh%Mm%Ss') + '-py_photos_organize_tpv.log'
		else:
			log_file_name='.//tmp//py_photos_organize_tpv.log'


	# Create a logger object:
	logger = logging.getLogger(__name__)
	# Setting the threshold of logger: file_log...
	logger.setLevel(logging.DEBUG)
	# Create and configure logger:
	logging.basicConfig(
		filename=log_file_name, 
		format='%(asctime)s %(name)s [%(process)d] %(levelname)s %(message)s', 
		filemode='w'
	)

	# Setting the threshold of logger: screen_log...
	coloredlogs.install(
		level='INFO', 
		logger=logger, 
		milliseconds=True, 
		fmt='%(asctime)s,%(msecs)03d %(levelname)s %(message)s' 
	)

	del(log_file_name)
	return(logger)

#----------------------------------------------------------------------------------------------#
# Reference: https://stackoverflow.com/questions/237079/how-to-get-file-creation-and-modification-date-times
# Reference: https://www.geeksforgeeks.org/how-to-get-file-creation-and-modification-date-or-time-in-python/
def get_filesystem_datetime(absolut_file_name: str = '', logger: logging.Logger = None) -> datetime:
	filesystem_datetime_create: float = 0.00
	filesystem_datetime: float = 0.00
	file_stats: os.stat_result = None
	datetime_filesystem: datetime = None

	if (len(absolut_file_name) > 1):
		if (platform.system() == 'Windows'):
			try:
				filesystem_datetime_create =os.path.getctime(absolut_file_name)
				try:
					filesystem_datetime = min(filesystem_datetime_create, os.path.getatime(absolut_file_name), os.path.getmtime(absolut_file_name))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033001 getting file system dates on Windows: {msg_e}".format(msg_e = e))
					else:
						raise e
			except Exception as e:
				if (logger is not None):
					logger.error("Error 20220313033100 getting file creation date on Windows: {msg_e}".format(msg_e = e))
				else:
					raise e
		else:
			try:
				file_stats = os.stat(absolut_file_name)
				filesystem_datetime_create = min(file_stats.st_birthtime)
				try:
					filesystem_datetime = min(filesystem_datetime_create, file_stats.st_mtime, file_stats.st_ctime)
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033101 getting file system dates: {msg_e}".format(msg_e = e))
					else:
						raise e
			except Exception as e:
				if (logger is not None):
					logger.error("Error 20220313033200 getting file creation date: {msg_e}".format(msg_e = e))
				else:
					raise e

		if (filesystem_datetime is not None):
			datetime_filesystem = datetime.datetime.fromtimestamp(filesystem_datetime)
		else:
			if (filesystem_datetime_create is not None):
				datetime_filesystem = datetime.datetime.fromtimestamp(filesystem_datetime_create)
			else:
				datetime_filesystem = None

	del(filesystem_datetime_create)
	del(filesystem_datetime)
	del(file_stats)
	return(datetime_filesystem)

#----------------------------------------------------------------------#
# Reading EXIF date information:
# Reference: https://orthallelous.wordpress.com/2015/04/19/extracting-date-and-time-from-images-with-python/
# Reference: https://github.com/vitords/sort-images/blob/master/sort_images.py
def get_metadata_datetime(absolut_file_name: str = '', logger: logging.Logger = None) -> datetime:
	image_file: Image = None
	exif_dict = {}
	exif_dict["0th"] = {}
	exif_dict["Exif"] = {}
	tmp_datetime_obtido: datetime = None
	datetime_metadata: datetime = None

	try:
		image_file = Image.open(absolut_file_name)
		exif_dict = piexif.load(image_file.info['exif'])
	except Exception as e:
		if (logger is not None):
			logger.error("Error 20220313062100 to get metadata EXIF: {msg_e}".format(msg_e=e))
		else:
			raise e

	if (len(exif_dict["Exif"]) > 0):

		exif_information = ''
		try:
			exif_information = image_file._getexif()[36867]
		except Exception as e:
			if (logger is not None):
				logger.error("Error 20220313062300 to get metadata EXIF 36867: {msg_e}".format(msg_e=e))
			else:
				raise e
		if (exif_information != ''):
			datetime_metadata = datetime.datetime.strptime(str(exif_information), '%Y:%m:%d %H:%M:%S')

		exif_information = ''
		try:
			exif_information = image_file._getexif()[36868]
		except Exception as e:
			if (logger is not None):
				logger.error("Error 20220313062600 to get metadata EXIF 36868: {msg_e}".format(msg_e=e))
			else:
				raise e
		if (exif_information != ''):
			tmp_datetime_obtido = datetime.datetime.strptime(exif_information, '%Y:%m:%d %H:%M:%S')
			if ((datetime_metadata is None) or (tmp_datetime_obtido < datetime_metadata)):
				datetime_metadata = tmp_datetime_obtido

	if (len(exif_dict["0th"]) > 0):

		exif_information = ''
		try:
			exif_information = str(exif_dict["0th"][306])
		except Exception as e:
			if (logger is not None):
				logger.error("Error 20220313063300 to get metadata EXIF 0TH306: {msg_e}".format(msg_e=e))
			else:
				raise e
		if (exif_information != ''):
			tmp_datetime_obtido = datetime.datetime.strptime(exif_information[2:21], '%Y:%m:%d %H:%M:%S')
			if ((datetime_metadata is None) or (tmp_datetime_obtido < datetime_metadata)):
				datetime_metadata = tmp_datetime_obtido

	del(exif_dict["0th"])
	del(exif_dict["Exif"])
	del(exif_dict)
	del(image_file)
	del(tmp_datetime_obtido)
	return datetime_metadata

#----------------------------------------------------------------------------------------------#
# Reference: https://docs.python.org/3/library/re.html
# Reference: https://github.com/excellentsport/picOrganizer
# Reference: https://regexland.com/regex-dates/
# Reference: https://datagy.io/python-return-multiple-values/
def get_filename_datetime(absolut_file_name: str = '', logger: logging.Logger = None) -> tuple:
	o_substring: str = ''
	o_second: str = ''
	o_minute: str = ''
	o_hour: str = ''
	o_day: str = ''
	o_month: str = ''
	o_year: str = ''
	o_filename_datetime: datetime = None
	datetime_regex: Pattern = None
	reg_exp_match = {}
	atual_impreciso: bool = False
	filename_datetime: datetime = None
	filename_text: string = ''

	# YYYY?MM?DD?hh?mm?ss:
	datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(\D)(0[1-9]|1[0-2])(\D)(0[1-9]|[1-2][0-9]|3[0-1])(\D)([0-1][0-9]|2[0-4])(\D)([0-5][0-9])(\D)([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[17:19]
				o_minute = o_substring[14:16]
				o_hour = o_substring[11:13]
				o_day = o_substring[8:10]
				o_month = o_substring[5:7]
				o_year = o_substring[0:4]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033600 converting date founded using YYYY?MM?DD?hh?mm?ss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# YYYYMMDD?hhmmss:
	datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])([\D])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[13:15]
				o_minute = o_substring[11:13]
				o_hour = o_substring[9:11]
				o_day = o_substring[6:8]
				o_month = o_substring[4:6]
				o_year = o_substring[0:4]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033700 converting date founded using YYYYMMDD?hhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# YYYYMMDDhhmmss:
	datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[12:14]
				o_minute = o_substring[10:12]
				o_hour = o_substring[8:10]
				o_day = o_substring[6:8]
				o_month = o_substring[4:6]
				o_year = o_substring[0:4]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033701 converting date founded using YYYYMMDDhhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# DDMMYYYY?hhmmss:
	datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])(0[1-9]|1[0-2])(19[7-9][0-9]|20[0-2][0-9])([\D])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[13:15]
				o_minute = o_substring[11:13]
				o_hour = o_substring[9:11]
				o_year = o_substring[4:8]
				o_month = o_substring[2:4]
				o_day = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033702 converting date founded using DDMMYYYY?hhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# DDMMYYYYhhmmss:
	datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])(0[1-9]|1[0-2])(19[7-9][0-9]|20[0-2][0-9])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[12:14]
				o_minute = o_substring[10:12]
				o_hour = o_substring[8:10]
				o_year = o_substring[4:8]
				o_month = o_substring[2:4]
				o_day = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033800 converting date founded using DDMMYYYYhhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# DD?MM?YYYY?hh?mm?ss:
	datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])(\D)(0[1-9]|1[0-2])(\D)(19[7-9][0-9]|20[0-2][0-9])(\D)([0-1][0-9]|2[0-4])(\D)([0-5][0-9])(\D)([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[17:19]
				o_minute = o_substring[14:16]
				o_hour = o_substring[11:13]
				o_year = o_substring[6:10]
				o_month = o_substring[3:5]
				o_day = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033900 converting date founded using DD?MM?YYYY?hh?mm?ss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# MMDDYYYY?hhmmss:
	datetime_regex = re.compile(r'(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])(19[7-9][0-9]|20[0-2][0-9])([\D])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[13:15]
				o_minute = o_substring[11:13]
				o_hour = o_substring[9:11]
				o_year = o_substring[4:8]
				o_day = o_substring[2:4]
				o_month = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033901 converting date founded using MMDDYYYY?hhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# MMDDYYYYhhmmss:
	datetime_regex = re.compile(r'(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])(19[7-9][0-9]|20[0-2][0-9])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[12:14]
				o_minute = o_substring[10:12]
				o_hour = o_substring[8:10]
				o_year = o_substring[4:8]
				o_day = o_substring[2:4]
				o_month = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313033905 converting date founded using MMDDYYYYhhmmss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False

	# MM?DD?YYYY?hh?mm?ss:
	datetime_regex = re.compile(r'(0[1-9]|1[0-2])(\D)(0[1-9]|[1-2][0-9]|3[0-1])(\D)(19[7-9][0-9]|20[0-2][0-9])(\D)([0-1][0-9]|2[0-4])(\D)([0-5][0-9])(\D)([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match is not None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[17:19]
				o_minute = o_substring[14:16]
				o_hour = o_substring[11:13]
				o_year = o_substring[6:10]
				o_day = o_substring[3:5]
				o_month = o_substring[0:2]
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger is not None):
						logger.error("Error 20220313034000 converting date founded using MM?DD?YYYY?hh?mm?ss: {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime is None) or (atual_impreciso) or ((o_filename_datetime < filename_datetime) and (o_second != '00') and (o_minute != '00') and (o_hour != '00'))):
					filename_text = o_substring
					filename_datetime = o_filename_datetime
					if ((o_second == '00') and (o_minute == '00') and (o_hour == '00')):
						atual_impreciso = True
					else:
						atual_impreciso = False
	del(o_substring)
	del(o_second)
	del(o_minute)
	del(o_hour)
	del(o_day)
	del(o_month)
	del(o_year)
	del(o_filename_datetime)
	del(atual_impreciso)
	del(datetime_regex)
	del(reg_exp_match)
	return filename_datetime, filename_text

#----------------------------------------------------------------------------------------------#
# Reference: https://pythonguides.com/python-find-substring-in-string/
# Reference: https://flaviocopes.com/python-get-file-details/
def get_new_absolut_path(min_escape_low_resolution: int = 0, folder_sufix: bool = False, original_absolut_file_name: str = '', file_date: datetime = None, date_type: str = '', folders_mask: str = '',  destination_dir: str = '', logger: logging.Logger = None) -> str:
	stats: os.stat_result = None
	new_subdir_date: str = ''
	absolute_destination_dir: str = ''
	dir_image_sufix: str = ''
	file_name_absolut_size: int = 0
	continue_execution: bool = True
	new_dir_destination: str = ''


	if ((folder_sufix) and ((original_absolut_file_name is None) or (len(original_absolut_file_name) < 1))):
		continue_execution = False
		if (logger is not None):
			logger.warning("Warning 20220313053300 - It's configured folder sufix without original file name.")

	if (file_date is None):
		continue_execution = False
		if (logger is not None):
			logger.warning("Warning 20220313053500 - Datetime stamp not defined.")

	if ((folders_mask is None) or (len(folders_mask) < 1)):
		continue_execution = False
		if (logger is not None):
			logger.warning("Warning 20220313053600 - Folder mask not defined.")

	if ((destination_dir is None) or (len(destination_dir) < 1)):
		continue_execution = False
		if (logger is not None):
			logger.warning("Warning 20220313053700 - Destination folder defined.")
	else:
		absolute_destination_dir = os.path.abspath(destination_dir)
		if (platform.system() == 'Windows'):
			if (absolute_destination_dir[-1:] != '\\'):
				absolute_destination_dir = absolute_destination_dir + '\\'
		else:
			if (absolute_destination_dir[-1:] != '//'):
				absolute_destination_dir = absolute_destination_dir + '//'
		new_dir_destination = absolute_destination_dir

	if (continue_execution == True):
		new_subdir_date = file_date.strftime(folders_mask)
		new_dir_destination = absolute_destination_dir + new_subdir_date

		if (folder_sufix):

			if (date_type == 'METADATA'):
				dir_image_sufix = 'metadata'

			if (('scr' in original_absolut_file_name.lower()) or ('capture' in original_absolut_file_name.lower())):
				dir_image_sufix = 'screen_capture'
			if (('insta' in original_absolut_file_name.lower()) or ('facebook' in original_absolut_file_name.lower())):
				dir_image_sufix = 'social_media'
			if (('message' in original_absolut_file_name.lower()) or ('telegram' in original_absolut_file_name.lower()) or ('whats' in original_absolut_file_name.lower()) or ('instant' in original_absolut_file_name.lower())):
				dir_image_sufix = 'instant_messages'

			#TODO: GEOTAG!

			if ((dir_image_sufix == '') and (min_escape_low_resolution > 0)):
				if (platform.system() == 'Windows'):
					try:
						file_name_absolut_size = os.path.getsize(original_absolut_file_name)
					except Exception as e:
						if (logger is not None):
							logger.error("Error 20220313051100 getting file size on Windows: {msg_e}".format(msg_e=e))
						else:
							raise e
				else:
					try:
						stats = os.stat(original_absolut_file_name)
						file_name_absolut_size = stats.st_size
					except Exception as e:
						if (logger is not None):
							logger.error("Error 20220313051200 getting file size: {msg_e}".format(msg_e=e))
						else:
							raise e
				if (file_name_absolut_size < min_escape_low_resolution):
					dir_image_sufix = 'low_resolution'

			if (dir_image_sufix != ''):
				new_dir_destination = new_dir_destination + '-'  + dir_image_sufix + '\\'

	if (platform.system() == 'Windows'):
		if (new_dir_destination[-1:] != '\\'):
			new_dir_destination = new_dir_destination + '\\'
	else:
		if (new_dir_destination[-1:] != '//'):
			new_dir_destination = new_dir_destination + '//'

	del(stats)
	del(new_subdir_date)
	del(absolute_destination_dir)
	del(dir_image_sufix)
	del(file_name_absolut_size)
	del(continue_execution)
	return new_dir_destination

#----------------------------------------------------------------------------------------------#
# Reference: https://www.freecodecamp.org/news/how-to-substring-a-string-in-python/
def get_new_file_name(file_date: DateTime = None, actual_file_name: str = '', prefix_file_mask: str = '', substring_remocao: str = '') -> str:
	tmp_file_name: str = ''
	rindex_dot: int = 0
	new_file_name: str = ''

	tmp_file_name = actual_file_name

	if (len(substring_remocao) > 0):
		tmp_file_name = actual_file_name.replace(substring_remocao+'s-', '')
		tmp_file_name = tmp_file_name.replace(substring_remocao, '')

	tmp_file_name = tmp_file_name.strip()

	rindex_dot = tmp_file_name.rindex('.')
	tmp_file_name = tmp_file_name[0:rindex_dot].replace('.', '-') + tmp_file_name[rindex_dot:]

	tmp_file_name = tmp_file_name.replace('(', '-')
	tmp_file_name = tmp_file_name.replace(')', '-')
	tmp_file_name = tmp_file_name.replace('[', '-')
	tmp_file_name = tmp_file_name.replace(']', '_')
	tmp_file_name = tmp_file_name.replace('--', '-')
	tmp_file_name = tmp_file_name.replace('--', '-')
	tmp_file_name = tmp_file_name.replace('--', '-')

	tmp_file_name = tmp_file_name.replace(' ', '_')
	tmp_file_name = tmp_file_name.replace('~', '_')
	tmp_file_name = tmp_file_name.replace('__', '_')
	tmp_file_name = tmp_file_name.replace('__', '_')
	tmp_file_name = tmp_file_name.replace('__', '_')

	tmp_file_name = tmp_file_name.replace('ç ', 'c')

	tmp_file_name = tmp_file_name.replace('ã', 'a')
	tmp_file_name = tmp_file_name.replace('á', 'a')
	tmp_file_name = tmp_file_name.replace('à', 'a')
	tmp_file_name = tmp_file_name.replace('ä', 'a')
	tmp_file_name = tmp_file_name.replace('â', 'a')

	tmp_file_name = tmp_file_name.replace('é', 'e')
	tmp_file_name = tmp_file_name.replace('é', 'e')
	tmp_file_name = tmp_file_name.replace('ë', 'e')
	tmp_file_name = tmp_file_name.replace('ê', 'e')
	
	tmp_file_name = tmp_file_name.replace('í', 'i')
	tmp_file_name = tmp_file_name.replace('ì', 'i')
	tmp_file_name = tmp_file_name.replace('ï', 'i')
	tmp_file_name = tmp_file_name.replace('î', 'i')

	tmp_file_name = tmp_file_name.replace('õ', 'o')
	tmp_file_name = tmp_file_name.replace('ó', 'o')
	tmp_file_name = tmp_file_name.replace('ò', 'o')
	tmp_file_name = tmp_file_name.replace('ö', 'o')
	tmp_file_name = tmp_file_name.replace('ô', 'o')

	tmp_file_name = tmp_file_name.replace('ú', 'u')
	tmp_file_name = tmp_file_name.replace('ù', 'u')
	tmp_file_name = tmp_file_name.replace('ü', 'u')
	tmp_file_name = tmp_file_name.replace('û', 'u')

	if (file_date is not None):
		new_file_name = file_date.strftime(prefix_file_mask)
	else:
		new_file_name = ''

	#TODO: GEOTAG!

	if (len(tmp_file_name)>100):
		new_file_name = new_file_name + '-' + tmp_file_name[-100:]
	else:
		new_file_name = new_file_name + '-' + tmp_file_name

	del(tmp_file_name)
	del(rindex_dot)
	return(new_file_name)

#----------------------------------------------------------------------------------------------#
def get_move_status(complete_old_file_name: str = '', complete_new_file_name: str = '', logger: logging.Logger = None) -> int:
	new_file_exist: bool = False
	old_file_exist: bool = False
	new_file_size:int = 0
	old_file_size:int = 0

	# 0 - Not exist both files, 1 - Only exist original/old, 2 - Only existe destination/new, 3 - Both files exist in different sizes, 4 - Both files in the same size
	status_return:int = 0

	try:
		if (os.path.exists(complete_new_file_name)):
			new_file_exist = True
		if (os.path.exists(complete_old_file_name)):
			old_file_exist = True
	except Exception as e:
		if (logger is not None):
			logger.error('Error 20220315051100 - The error thrown was {err_msg}'.format(err_msg=e))
		else:
			raise e

	if (old_file_exist):
		if (new_file_exist):
			status_return = 3 # Both files exist in different sizes
		else:
			status_return = 1 # Only exist original/old
	else:
		if (new_file_exist):
			status_return = 2 # Only existe destination/new
		else:
			status_return = 2 # Not exist both files

	if (status_return > 2):
		try:
			new_file_size = os.path.getsize(complete_new_file_name)
			old_file_size = os.path.getsize(complete_old_file_name)
		except Exception as e:
			if (logger is not None):
				logger.error('Error 20220315051000 - The error thrown was {err_msg}'.format(err_msg=e))
			else:
				raise e
		if ((old_file_size) == (new_file_size)):
			status_return = 4 # Both files in the same size
		else:
			status_return = 3 # Both files exist in different sizes
		logger.debug('Size of old/original file: ' + str(old_file_size))
		logger.debug('Size of new/destination file: ' + str(new_file_size))

	del(new_file_exist)
	del(old_file_exist)
	del(new_file_size)
	del(old_file_size)
	return(status_return)

#----------------------------------------------------------------------------------------------#
# MAIN: #
#----------------------------------------------------------------------------------------------#
# Reference: https://docs.python.org/3/library/datetime.html
# Reference: https://pynative.com/python-datetime-format-strftime/
# Reference: https://code-paper.com/python/examples-python-datetime-convert-float-to-date
def main():

	# Obtain parameters from the system call:
	files_orign: str = args.files_orign
	files_destination: str = args.files_destination
	folders: str = args.folders
	files_prefix: str = args.files_prefix
	overwrite: str = args.overwrite
	batch_quantity_files: int = args.batch_quantity_files
	min_size_escape_low_resolution: int = args.min_size_escape_low_resolution
	generate_folder_sufix: bool = args.generate_folder_sufix
	rename_file: bool = args.rename_file
	timestamp_log: bool = args.timestamp_log

	logger: logging.Logger = log_inicialization(timestamp_log)

	logger.info('---------- << pyPhotosOrganizeTPV >> ----------')
	logger.info('Starting script version [' + PROJECT_VERSION + '] doing <<' + PROJECT_DOING + '>>...')

	now = datetime.datetime.now()
	logger.debug('------ Arguments / Parameters:')
	logger.debug('Files Orign (INPUT parameter):')
	logger.debug(files_orign)
	logger.debug('Files Destination (OUTPUT parameter):')
	logger.debug(files_destination)
	logger.debug('Folders mask: '+ folders)
	logger.debug('Files prefix mask: '+ files_prefix)

	overwrite = overwrite.lower()
	overwrite = overwrite[0:1]
	if (overwrite == 'o'):
		logger.warning('If file exist on destination, it will be overwrited in the destination folder!')
	else:
		if (overwrite == 'i'):
			logger.warning('If file exist on destination, it will ignored in the original folder!')
		else:
			logger.debug('If file exist on destination, it will be duplicated in the destination folder!')
			if (overwrite != 'd'):
				logger.warning('Option to overwrite invalid!')
				overwrite = 'd'

	logger.debug('------ Test:')
	logger.debug('Showing datetime in folder format: ' +  now.strftime(folders))
	logger.debug('Showing datetime in prefix format: ' + now.strftime(files_prefix))

	logger.debug('')
	logger.debug('------ Starting file process...')

	counter_files_processed: int = 0
	counter_files_on_destination: int = 0
	file_name: str = ''
	file_name_absolut: str = ''

	if (batch_quantity_files > 0):
		msg_max_file_processed = ' to maximum '+ str(batch_quantity_files) +' files...'
	else:
		batch_quantity_files = 0
		msg_max_file_processed = ' to all files in orign folder...'

	for original_path, original_subdir, original_file in os.walk(files_orign):

		for file_name in original_file:

			file_name_absolut = os.path.abspath(str(pathlib.PurePath(original_path, file_name)))

			if (file_name.lower().endswith(ALL_EXTENSIONS)):
				counter_files_processed = counter_files_processed + 1

				if ((batch_quantity_files == 0) or (counter_files_processed <= batch_quantity_files)):

					logger.info('')
					logger.info('--- Processing file #' + str(counter_files_processed) + msg_max_file_processed)
					logger.info('Absolut file name:')
					logger.info(file_name_absolut)

					file_datetime_type: str = ''
					filename_datetime_text: str = ''
					file_datetime_stamp: datetime = None

					#----------------------------------------------------------------------#
					# Reading metadata date information:
					metadata_file_datetime: datetime = None
					metadata_file_datetime = get_metadata_datetime(absolut_file_name = file_name_absolut, logger = logger)

					if (metadata_file_datetime is not None):
						logger.debug('Metadata datetime stamp: ' + str(metadata_file_datetime))
						if ((file_datetime_stamp is None) or (file_datetime_stamp > metadata_file_datetime)):
							file_datetime_type = 'METADATA'
							file_datetime_stamp = metadata_file_datetime
					else:
						logger.debug('No datetime from metadata!')

					#----------------------------------------------------------------------#
					# Reading date from Filesystem:
					filesystem_file_datetime:datetime = None
					filesystem_file_datetime = get_filesystem_datetime(absolut_file_name = file_name_absolut, logger = logger)

					if (filesystem_file_datetime is not None):
						logger.debug('Filesystem datetime stamp: ' + str(filesystem_file_datetime))
						if ((file_datetime_stamp is None) or (file_datetime_stamp > filesystem_file_datetime)):
							file_datetime_type = 'FILESYSTEM'
							file_datetime_stamp = filesystem_file_datetime
					else:
						logger.debug('No datetime from filesystem!')

					#----------------------------------------------------------------------#
					# Reading date information from file name using RegEx:
					filename_file_datetime: datetime = None
					filename_file_datetime, filename_datetime_text = get_filename_datetime(file_name_absolut, logger)

					if (filename_file_datetime is not None):
						logger.debug('File name datetime stamp: ' + str(filename_file_datetime))
						if ((file_datetime_stamp is None) or (file_datetime_stamp > filename_file_datetime)):
							file_datetime_type = 'FILENAME'
							file_datetime_stamp = filename_file_datetime
					else:
						logger.debug('No datetime from filename!')

					#----------------------------------------------------------------------#
					# Reading metadata date information:
					geodata_resume: str = ''
					geodata_resume = get_geodata_exif(absolut_file_name = file_name_absolut, logger = logger)

					if (geodata_resume != ''):
						logger.debug('Geodata: {geodata_resume}').format(geodata_resume)
					else:
						logger.debug('No geodata from metadata!')

					#----------------------------------------------------------------------#
					# Creating new file name, absolut path and absolut file name:

					new_file_name: str = ''
					new_absolut_path: str = ''
					new_absolut_file_name: str = ''
					substring_remocao: str = ''

					if ((len(file_name) <1) or (file_datetime_stamp is None)):
						logger.warnning('Warn 20220313044000 - Impossible obtain a datetime stamp for file {msg_filename}'.format(msg_filename = file_name))

					else:

						logger.debug('Using [' + file_datetime_type + ']...')

						#----------------------------------------------------------------------#
						# Creating new name of file:
						if (rename_file):
							if ((filename_file_datetime is not None) and (len(filename_datetime_text)>0)):
								substring_remocao = filename_datetime_text
								logger.debug('Removing substring <<' + substring_remocao + '>> from filename...')
							else:
								substring_remocao = ''
							new_file_name = get_new_file_name(file_datetime_stamp, file_name, files_prefix, substring_remocao)
						else:
							new_file_name = file_name

						#----------------------------------------------------------------------#
						# Creating new absolut file path:
						new_absolut_path = get_new_absolut_path(min_size_escape_low_resolution, generate_folder_sufix, file_name_absolut, file_datetime_stamp, file_datetime_type, folders, files_destination, logger)

						#----------------------------------------------------------------------#
						# Creating new absolut file name:
						if (platform.system() == 'Windows'):
							if (new_absolut_path[-1:] != '\\'):
								new_absolut_file_name = new_absolut_path + '\\' + new_file_name
							else:
								new_absolut_file_name = new_absolut_path + new_file_name
						else:
							if (new_absolut_path[-1:] != '//'):
								new_absolut_file_name = new_absolut_path + '//' + new_file_name
							else:
								new_absolut_file_name = new_absolut_path + new_file_name

						logger.info('New absolut file name:')
						logger.info(new_absolut_file_name)

						#----------------------------------------------------------------------#
						# Moving original file to new destiny:
						file_was_on_destiny:bool = False
						new_absolut_file_name_used: str = ''
						status_copia: int = -1

						if not os.path.exists(new_absolut_path):
							os.makedirs(new_absolut_path)

						file_was_on_destiny, new_absolut_file_name_used = tpv_move_file(file_name_absolut, new_absolut_file_name, overwrite, logger)

						if (file_was_on_destiny):
							counter_files_on_destination = counter_files_on_destination + 1
							logger.warning('It was exist a file on destination!')

						# 0 - Not exist both files, 1 - Only exist original/old, 2 - Only existe destination/new, 3 - Both files exist in different sizes, 4 - Both files in the same size
						status_copia = get_move_status(file_name_absolut, new_absolut_file_name_used, logger)

						if ((overwrite != 'i') and (status_copia != 2)):
							if (status_copia == 3):
								logger.error('Erro 20220315042300: Both files are continue existing in differente size!')
								logger.warning('Ignoring files!')
							if (status_copia == 4):
								logger.error('Erro 20220315030900: Both files are continue existing!')
								logger.warning('Removing oringal file!')
								try:
									os.remove(file_name_absolut)
									#os.unlink(file_name_absolut)
									logger.debug('Oringal file removed!')
								except Exception as e:
									logger.error('Error 20200315033300 removing original file: {err_msg}'.format(err_msg=e))

				else:
					logger.debug('File ignored - batch limit: ' + str(batch_quantity_files) + ' - file ' + str(file_name_absolut))
			else:
				logger.debug('File ignored (extension): ' + str(file_name_absolut))

	if (counter_files_on_destination > 0):
		logger.warning('Images pre-existents on destine: '+str(counter_files_on_destination))
	logger.debug('')
	logger.debug('------ Fineshed!')
	sys.exit(0)

#----------------------------------------------------------------------------------------------#
if __name__ == '__main__':
	main()