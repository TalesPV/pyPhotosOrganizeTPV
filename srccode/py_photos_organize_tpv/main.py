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
import coloredlogs
import piexif
import argparse
import exifread

from xmlrpc.client import Boolean, DateTime
from PIL import Image
from asyncio import exceptions
from pickle import FALSE
from GPSPhoto import gpsphoto

# Obtain parameters from the system call:

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-f', '--folders', type=str, required=False, default='%Y_%m')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')
parser.add_argument('-q', '--batch_quantity_files', type=int, required=False, default=0)
parser.add_argument('-y', '--exif_min_year_discart_date', type=int, required=False, default=1990)
parser.add_argument('-s', '--min_size_escape_low_resolution', type=int, required=False, default=200000)
parser.add_argument('-g', '--generate_folder_sufix', type=bool, required=False, default=True)
parser.add_argument('-n', '--rename_file', type=bool, required=False, default=True)
parser.add_argument('-l', '--timestamp_log', type=bool, required=False, default=True)

args = parser.parse_args()

# Version:
PROJECT_VERSION = '1.0.0.20220313000000'
PROJECT_DOING = 'Refectoring to functions.'

# Define extensions to be processed and to obtain metadata:
IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.gif', '.bmp', '.tif')
VIDEO_EXTENSIONS = ('.mov', '.mp4', '.avi', '.mov')
MSOFFICE_EXTENSIONS = ('.doc', '.docx', '.xls', '.xlsx')
OTHER_EXTENSIONS = ('.pdf', )
ALL_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + MSOFFICE_EXTENSIONS + OTHER_EXTENSIONS


#----------------------------------------------------------------------------------------------#
# Reference: https://pypi.org/project/coloredlogs/
def log_inicialization(log_with_timestamp: Boolean = False) -> logging.Logger:

	log_file_name = None

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


	# Create a logger object.
	logger = logging.getLogger(__name__)
	# Setting the threshold of logger to DEBUG
	logger.setLevel(logging.DEBUG)
	# Create and configure logger
	logging.basicConfig(
		filename=log_file_name, 
		format='%(asctime)s %(name)s [%(process)d] %(levelname)s %(message)s', 
		filemode='w'
	)

	coloredlogs.install(
		level='DEBUG', 
		logger=logger, 
		milliseconds=True, 
		fmt='%(asctime)s,%(msecs)03d %(levelname)s %(message)s' 
	)

	return logger

#----------------------------------------------------------------------------------------------#
# Reference: https://stackoverflow.com/questions/237079/how-to-get-file-creation-and-modification-date-times
# Reference: https://www.geeksforgeeks.org/how-to-get-file-creation-and-modification-date-or-time-in-python/
def get_filesystem_datetime(logger: logging.Logger, absolut_file_name: str) -> datetime:
	filesystem_datetime_create = None
	filesystem_datetime = None
	datetime_filesystem = None

	if (platform.system() == 'Windows'):
		try:
			filesystem_datetime_create =os.path.getctime(absolut_file_name)
			try:
				filesystem_datetime = min(filesystem_datetime_create, os.path.getatime(absolut_file_name), os.path.getmtime(absolut_file_name))
			except Exception as e:
				logger.error(str(e))
		except Exception as e:
			logger.error(str(e))
	else:
		try:
			stats = os.stat(absolut_file_name)
			filesystem_datetime_create = min(stats.st_birthtime)
			try:
				filesystem_datetime = min(filesystem_datetime_create, stats.st_mtime, stats.st_ctime)
			except Exception as e:
				logger.error(str(e))
		except Exception as e:
			logger.error(str(e))

	if (filesystem_datetime != None):
		datetime_filesystem = datetime.datetime.fromtimestamp(filesystem_datetime)
	else:
		if (filesystem_datetime_create != None):
			datetime_filesystem = datetime.datetime.fromtimestamp(filesystem_datetime_create)
		else:
			datetime_filesystem = None

	return datetime_filesystem

#----------------------------------------------------------------------------------------------#
# Reference: https://docs.python.org/3/library/re.html
# Reference: https://github.com/excellentsport/picOrganizer
# Reference: https://regexland.com/regex-dates/
# Reference: https://datagy.io/python-return-multiple-values/
def get_filename_datetime(absolut_file_name: str = '', logger: logging.Logger = None) -> tuple:

	filename_datetime: datetime = None
	filename_text: string = ''

	o_filename_datetime: datetime = None
	o_substring: str = ''
	o_second: str = ''
	o_minute: str = ''
	o_hour: str = ''
	o_day: str = ''
	o_month: str = ''
	o_year: str = ''

	# YYYY?MM?DD?hh?mm?ss:
	datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(\D)(0[1-9]|1[0-2])(\D)(0[1-9]|[1-2][0-9]|3[0-1])(\D)([0-1][0-9]|2[0-4])(\D)([0-5][0-9])(\D)([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match != None):
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
					if (logger != None):
						logger.error("The error thrown was {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime == None) or (o_filename_datetime < filename_datetime)):
					filename_text = o_substring
					filename_datetime = o_filename_datetime

	# YYYYMMDD?hhmmss:
	datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])([\D])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match != None):
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
					if (logger != None):
						logger.error("The error thrown was {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime == None) or (o_filename_datetime < filename_datetime)):
					filename_text = o_substring
					filename_datetime = o_filename_datetime

	# DDMMYYYY?hhmmss:
	datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])(0[1-9]|1[0-2])(19[7-9][0-9]|20[0-2][0-9])([\D])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match != None):
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
					if (logger != None):
						logger.error("The error thrown was {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime == None) or (o_filename_datetime < filename_datetime)):
					filename_text = o_substring
					filename_datetime = o_filename_datetime

	# DD?MM?YYYY?hh?mm?ss:
	datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])(\D)(0[1-9]|1[0-2])(\D)(19[7-9][0-9]|20[0-2][0-9])(\D)([0-1][0-9]|2[0-4])(\D)([0-5][0-9])(\D)([0-5][0-9])')
	for reg_exp_match in datetime_regex.finditer(absolut_file_name):
		if (reg_exp_match != None):
			o_substring = reg_exp_match.group(0)
			if (len(o_substring) > 0):
				o_second = o_substring[17:19]
				o_minute = o_substring[14:16]
				o_hour = o_substring[11:13]
				o_year = o_substring[6:10]
				o_month = o_substring[3:5]
				o_day = o_substring[0:2]
				print('===>>> RegEx: ' + o_substring + ', Year: '+ o_year + ', Month: ' + o_month + ', Day: ' + o_day)
				try:
					o_filename_datetime = datetime.datetime(int(o_year), int(o_month), int(o_day), int(o_hour), int(o_minute), int(o_second))
				except Exception as e:
					if (logger != None):
						logger.error("The error thrown was {msg_e}".format(msg_e=e))
					else:
						raise e
				if ((filename_datetime == None) or (o_filename_datetime < filename_datetime)):
					filename_text = o_substring
					filename_datetime = o_filename_datetime

	return filename_datetime, filename_text

#----------------------------------------------------------------------------------------------#
def get_new_absolut_path(file_date: datetime, folders_mask: str,  destination_dir: str, logger: logging.Logger = None) -> str:
	new_dir_destination = None
	new_subdir_date = None
	absolute_destination_dir = None

	absolute_destination_dir =  os.path.abspath(destination_dir)


	if ((file_date != None) and (folders_mask != None) and (folders_mask != '')):
		if (platform.system() == 'Windows'):
			if (absolute_destination_dir[-1:] != '\\'):
				absolute_destination_dir = absolute_destination_dir + '\\'
		else:
			if (absolute_destination_dir[-1:] != '//'):
				absolute_destination_dir = absolute_destination_dir + '//'
		new_subdir_date = file_date.strftime(folders_mask)
		new_dir_destination = absolute_destination_dir + new_subdir_date

	if ((new_dir_destination[-1:] == '\\') or (new_dir_destination[-1:] == '//')):
			new_dir_destination = new_dir_destination[0:-1]

	return new_dir_destination

#----------------------------------------------------------------------------------------------#
# Reference: https://www.freecodecamp.org/news/how-to-substring-a-string-in-python/
def get_new_file_name(file_date: DateTime = None, actual_file_name: str = '', prefix_file_mask: str = '', substring_remocao: str = '') -> str:
	new_file_name: str = ''
	tmp_file_name: str = ''
	quantidade_de_pontos: int = 0

	tmp_file_name = actual_file_name

	if (len(substring_remocao) > 0):
		tmp_file_name = actual_file_name.replace(substring_remocao, '')

	tmp_file_name = tmp_file_name.strip()

	quantidade_de_pontos = tmp_file_name[-5:].count('.')
	if (quantidade_de_pontos == 1):
		tmp_file_name = tmp_file_name[0:-5].replace('.', '-') + tmp_file_name[-5:]

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

	if (file_date != None):
		if (len(tmp_file_name)>100):
			new_file_name = file_date.strftime(prefix_file_mask) + '-' + tmp_file_name[-100:]
		else:
			new_file_name = file_date.strftime(prefix_file_mask) + '-' + tmp_file_name

	return new_file_name

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
			new_file_size = os.path.getsize(complete_new_file_name)

		if (os.path.exists(complete_old_file_name)):
			old_file_exist = True
			old_file_size = os.path.getsize(complete_old_file_name)

	except Exception as e:
		if (logger != None):
			logger.error('The error thrown was {err_msg}'.format(err_msg=e))
		else:
			raise e

	if ((old_file_exist) and (logger != None)):
		logger.debug('Size of old/original file: ' + str(old_file_size))

	if ((new_file_exist) and (logger != None)):
		logger.debug('Size of new/destination file: ' + str(new_file_size))

	if (old_file_exist):
		if (new_file_exist):
			if ((old_file_size) == (new_file_size)):
				status_return = 4 # Both files in the same size
			else:
				status_return = 3 # Both files exist in different sizes
		else:
			status_return = 1 # Only exist original/old
	else:
		if (new_file_exist):
			status_return = 2 # Only existe destination/new
		else:
			status_return = 2 # Not exist both files

	return status_return

'''
#----------------------------------------------------------------------------------------------#
# MAIN: #
#----------------------------------------------------------------------------------------------#
# Reference: https://stackoverflow.com/questions/2909975/python-list-directory-subdirectory-and-files#2909998
# Reference: https://docs.python.org/3/library/datetime.html
# Reference: https://pynative.com/python-datetime-format-strftime/
# Reference: https://code-paper.com/python/examples-python-datetime-convert-float-to-date
'''
def main():

	# Obtain parameters from the system call:
	files_orign: str = args.files_orign
	files_destination: str = args.files_destination
	folders: str = args.folders
	files_prefix: str = args.files_prefix
	batch_quantity_files: int = args.batch_quantity_files
	exif_min_year_discart_date: int = args.exif_min_year_discart_date
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
	
	logger.debug('------ Test:')
	logger.debug('Showing datetime in folder format: ' +  now.strftime(folders))
	logger.debug('Showing datetime in prefix format: ' + now.strftime(files_prefix))

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

			if (file_name.endswith(ALL_EXTENSIONS)):
				counter_files_processed = counter_files_processed + 1

				if ((batch_quantity_files == 0) or (counter_files_processed <= batch_quantity_files)):

					logger.info('--- Processing file #' + str(counter_files_processed) + msg_max_file_processed)
					logger.info('Absolut file name:')
					logger.info(file_name_absolut)

					file_datetime_type: str = ''
					exif_utilizado: str = ''
					filename_datetime_text: str = ''
					dir_image_sufix: str = ''
					dir_destination: str = ''
					file_datetime_stamp: datetime = None

					#----------------------------------------------------------------------#
					# Reading date from Filesystem:
					filesystem_file_datetime:datetime = None
					filesystem_file_datetime = get_filesystem_datetime(logger, file_name_absolut)

					if (filesystem_file_datetime != None):
						logger.debug('Filesystem datetime stamp: ' + str(filesystem_file_datetime))
						if ((file_datetime_stamp == None) or (file_datetime_stamp > filesystem_file_datetime)):
							file_datetime_type = 'FILESYSTEM'
							file_datetime_stamp = filesystem_file_datetime
						else:
							logger.debug('Ignoring [FILESYSTEM], using [' + file_datetime_type + ']...')
					else:
						logger.debug('No datetime from filesystem!')


					#----------------------------------------------------------------------#
					# Reading date information from file name using RegEx:
					filename_file_datetime: datetime = None
					filename_file_datetime, filename_datetime_text = get_filename_datetime(file_name_absolut, logger)

					if (filename_file_datetime != None):
						logger.debug('File name datetime stamp: ' + str(filename_file_datetime))
						if ((file_datetime_stamp == None) or (file_datetime_stamp > filename_file_datetime)):
							file_datetime_type = 'FILENAME'
							file_datetime_stamp = filename_file_datetime
						else:
							logger.debug('Ignoring [FILENAME], using [' + file_datetime_type + ']...')
					else:
						logger.debug('No datetime from filename!')

					#----------------------------------------------------------------------#
					# Reading EXIF date information:
					# Reference: https://orthallelous.wordpress.com/2015/04/19/extracting-date-and-time-from-images-with-python/
					# Reference: https://github.com/vitords/sort-images/blob/master/sort_images.py
					try:
						image = Image.open(file_name_absolut)
						exif_dict = piexif.load(image.info['exif'])
						#logger.debug('EXIF loaded successfuly.')
					except WindowsError as e:
						logger.error("The error thrown was {e}".format(e=e))
					except KeyError:
						logger.debug('No Exif data!')
						exif_dict = {}
						exif_dict["0th"] = {}
						exif_dict["Exif"] = {}

					if (len(exif_dict["Exif"]) > 0):

						exif_information = ''
						try:
							exif_information = image._getexif()[36867]
						except KeyError:
							logger.debug('Key 36867 not found!')

						if (exif_information != ''):
							#logger.warning('EXIF[36867]: ' + str(exif_information))
							if (int(exif_information[0:4]) >= exif_min_year_discart_date):
								if (exif_utilizado == ''):
									date_dir_destination = datetime.datetime.strptime(str(exif_information), '%Y:%m:%d %H:%M:%S')
									dir_image_sufix = 'exif'
									exif_utilizado = '36867'

						exif_information = ''
						try:
							exif_information = image._getexif()[36868]
						except KeyError:
							logger.debug('Key 36868 not found!')

						if (exif_information != ''):
							#logger.warning('EXIF[36868]: ' + str(exif_information))
							if (int(exif_information[0:4]) >= exif_min_year_discart_date):
								if ((exif_utilizado == '') or (date_dir_destination > datetime.datetime.strptime(exif_information, '%Y:%m:%d %H:%M:%S'))):
									date_dir_destination = datetime.datetime.strptime(exif_information, '%Y:%m:%d %H:%M:%S')
									dir_image_sufix = 'exif'
									exif_utilizado = '36868'

					if (len(exif_dict["0th"]) > 0):

						exif_information = ''
						try:
							exif_information = str(exif_dict["0th"][306])
						except KeyError:
							logger.debug('Key 0TH306 not found!')

						if (exif_information != ''):
							exif_information = str(exif_dict["0th"][306])
							#logger.warning('EXIF[TH306]: ' + str(exif_information[2:21]))
							if (int(exif_information[2:6]) >= exif_min_year_discart_date):
								if ((exif_utilizado == '') or (date_dir_destination > datetime.datetime.strptime(exif_information[2:21], '%Y:%m:%d %H:%M:%S'))):
									date_dir_destination = datetime.datetime.strptime(exif_information[2:21], '%Y:%m:%d %H:%M:%S')
									dir_image_sufix = 'exif'
									exif_utilizado = 'TH306'

					if (exif_utilizado != ''):
						dir_destination = date_dir_destination.strftime(folders)
						if (rename_file == False):
							new_file_name = file_name
						else:
							new_file_name = file_name.lower().strip()
							if (len(file_name)>100):
								new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name[-100:]
							else:
								new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name
						logger.debug('File name from EXIF ('+ exif_utilizado +'): ' + str(date_dir_destination))
					else:
						logger.debug('No date from EXIF!')

					#----------------------------------------------------------------------#
					# Reading Geodata information:
					# Reference: https://towardsdatascience.com/grabbing-geodata-from-your-photos-library-using-python-60eb0462e147
					#try:
						#geodata = gpsphoto.getGPSData(file_name_absolut)
						#logger.debug('GeoData: ' + str(geodata))
					#except KeyError:
						#logger.error('GeoData with erros!')


					#----------------------------------------------------------------------#
					# Creating new absolut file name:
					new_absolut_path = None
					new_file_name = None
					new_absolut_file_name = None

					substring_remocao: str = ''

					print('====> filename_datetime_text: ' + filename_datetime_text)

					if (file_datetime_type == 'FILENAME'):
						substring_remocao = filename_datetime_text

					print('====> substring_remocao: ' + substring_remocao)

					new_absolut_path = get_new_absolut_path(logger = logger, file_date = file_datetime_stamp, folders_mask = folders, destination_dir = files_destination)

					if (rename_file):
						new_file_name = get_new_file_name(file_datetime_stamp, file_name, files_prefix, substring_remocao)
					else:
						new_file_name = file_name

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

					logger.debug('Old filename:')
					logger.debug(file_name_absolut)
					logger.debug('New filename:')
					logger.debug(new_absolut_file_name)

					#----------------------------------------------------------------------#
					# Generating folder sufix:
					# Reference: https://pythonguides.com/python-find-substring-in-string/
					# Reference: https://flaviocopes.com/python-get-file-details/

					file_name_absolut_size = 0
					if platform.system() == 'Windows':
						file_name_absolut_size = os.path.getsize(file_name_absolut)
					else:
						stats = os.stat(file_name_absolut)
						file_name_absolut_size = stats.st_size
					if (file_name_absolut_size < min_size_escape_low_resolution):
						dir_image_sufix = 'low_resolution'

					if ('insta' in file_name_absolut.lower()):
						dir_image_sufix = 'social_media'
					if (('instagram' in file_name_absolut.lower()) or ('facebook' in file_name_absolut.lower())):
						dir_image_sufix = 'social_media'
					if (('message' in file_name_absolut.lower()) or ('telegram' in file_name_absolut.lower()) or ('whats' in file_name_absolut.lower()) or ('instant' in file_name_absolut.lower())):
						dir_image_sufix = 'instant_messages'
					if (('screen' in file_name_absolut.lower()) or ('capture' in file_name_absolut.lower())):
						dir_image_sufix = 'screen_capture'

					logger.debug('Sufixo encontrado no nome: ' + dir_image_sufix)

					if (generate_folder_sufix):
						new_file_dir = files_destination + dir_destination + '-'  + dir_image_sufix + '\\'
					else:
						new_file_dir = files_destination + dir_destination + '\\'

					complete_path_new_file = str(new_file_dir + new_file_name).lower()
					logger.info('New file and folder: ' + complete_path_new_file)

					if not os.path.exists(new_file_dir):
						os.makedirs(new_file_dir)

					arquivo_movido = False
					arquivo_copiado = False

					if os.path.exists(complete_path_new_file):
						try:
							logger.debug('Tamanho origem: ' + str(os.path.getsize(file_name_absolut)))
							logger.debug('Tamanho destino: ' + str(os.path.getsize(complete_path_new_file)))
							if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
								counter_files_on_destination = counter_files_on_destination + 1
								'''
								try:
									os.unlink(file_name_absolut)
									arquivo_movido = True
								except WindowsError as e:
									logger.info('Erro 0004')
									#logger.error("The error thrown was {e}".format(e=e))
									if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
										logger.info('Esperando 10s...')
										time.sleep(1)
										try:
											os.remove(file_name_absolut)
											arquivo_movido = True
										except WindowsError as e:
											logger.error("The error thrown was {e}".format(e=e))
								'''
						except Exception as e:
							logger.error("The error thrown was {e}".format(e=e))

					'''
					if (arquivo_movido == False):
						try:
							shutil.move(file_name_absolut, complete_path_new_file)
							arquivo_movido = True
							logger.info('Image was moved.')
						except Exception as e:
							logger.info('Erro 0002')
							#logger.error("There was an error copying {picture} to {target}".format(picture=file_name_absolut,target=complete_path_new_file))
							#logger.error("The error thrown was {e}".format(e=e))

					if (arquivo_movido == False):
						try:
							os.rename(file_name_absolut, complete_path_new_file)
							arquivo_movido = True
							logger.info('Image was renamed.')
						except Exception as e:
							logger.info('Erro 0001')
							#logger.error("The error thrown was {e}".format(e=e))
					'''

					'''
					if (arquivo_movido == False):
						try:
							#os.link(file_name_absolut, complete_path_new_file)
							#os.remove(file_name_absolut)
							arquivo_movido = True
							logger.info('Image was copied and deleted.')
						except PermissionError:
							logger.error('Error trying to rename file.')
					'''

					'''
					if (arquivo_movido == False):
						if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
							try:
								#os.remove(file_name_absolut)
								os.system('move /y "{origem}" "{destino}"'.format(origem=file_name_absolut, destino=complete_path_new_file))
							except Exception as e:
								logger.error("The error thrown was {e}".format(e=e))
					'''

				else:
					logger.debug('File ignored - batch limit: ' + str(batch_quantity_files) + ' - file ' + str(file_name_absolut))
			else:
				logger.debug('File ignored (extension): ' + str(file_name_absolut))

	if (counter_files_on_destination >0):
		logger.warning('Images pre-existents on destine: '+str(counter_files_on_destination))
	sys.exit(0)

#----------------------------------------------------------------------------------------------#
if __name__ == '__main__':
	main()