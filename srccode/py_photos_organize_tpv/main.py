from xmlrpc.client import DateTime
from PIL import Image
# Reference: https://www.geeksforgeeks.org/working-images-python/

import os
import platform
import re
import sys
import pathlib

import datetime
import time
# Reference:  https://www.codevscolor.com/python-print-date-time-hour-minute
# Reference: https://www.programiz.com/python-programming/datetime
# Reference: https://www.tutorialspoint.com/How-to-print-current-date-and-time-using-Python

import shutil

import coloredlogs
# Reference: https://pypi.org/project/coloredlogs/
# Reference: https://coloredlogs.readthedocs.io/en/latest/readme.html
# Reference: https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output

import logging
# Reference: https://www.geeksforgeeks.org/logging-in-python/

import piexif
from asyncio import exceptions
from pickle import FALSE
import argparse

import exifread
from GPSPhoto import gpsphoto

# Basic References:
# https://www.youtube.com/watch?v=--_K4G3HCcI
# https://blog.gunderson.tech/26307/using-virtual-environment-requirements-txt-with-python
# https://www.programiz.com/python-programming/datetime/strftime

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-f', '--folders', type=str, required=False, default='%Y_%m')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')
parser.add_argument('-q', '--batch_quantity_images', type=int, required=False, default=0)
parser.add_argument('-y', '--exif_min_year_discart_date', type=int, required=False, default=1990)
parser.add_argument('-s', '--min_size_escape_low_resolution', type=int, required=False, default=200000)
parser.add_argument('-g', '--generate_folder_sufix', type=bool, required=False, default=True)
# min_width_escape_low_resolution
# 
# generate_folder_sufix : exif, instante_message, screen, low_resolution, file_system, name_date, others
# rename_file

args = parser.parse_args()

# Define what image and video file extensions to search for:
IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.gif')
VIDEOS_EXTENSIONS = ('.mov', 'mp4')

#----------------------------------------------------------------------------------------------#
def log_inicialization():
	# Create a logger object.
	logger = logging.getLogger(__name__)
	# Setting the threshold of logger to DEBUG
	logger.setLevel(logging.DEBUG)
	# Create and configure logger
	logging.basicConfig(
		filename='.\\tmp\\' + datetime.datetime.strftime(datetime.datetime.now(), '%Y_%m_%d_%Hh%Mm%Ss') + '-py_photos_organize_tpv.log', 
		format='%(asctime)s %(name)s [%(process)d] %(levelname)s %(message)s', 
		filemode='w'
	)

	# Reference: https://pypi.org/project/coloredlogs/
	coloredlogs.install(
		#level='DEBUG', 
		logger=logger, 
		milliseconds=True, 
		fmt='%(asctime)s,%(msecs)03d %(levelname)s %(message)s' 
	)

	return logger

#----------------------------------------------------------------------------------------------#
def main():
	files_orign = args.files_orign
	files_destination = args.files_destination
	folders = args.folders
	files_prefix = args.files_prefix
	batch_quantity_images = args.batch_quantity_images
	exif_min_year_discart_date = args.exif_min_year_discart_date
	generate_folder_sufix = args.generate_folder_sufix
	min_size_escape_low_resolution = args.min_size_escape_low_resolution

	files_orign = 'D:\\dropbox\\fotos-tpv\\_organizar\\'
	#batch_quantity_images = 100

	logger = log_inicialization()

	logger.info('<< pyPhotosOrganizeTPV >>')

	logger.info('Starting script...')

	now = datetime.datetime.now()
	logger.info('Arguments:')
	logger.info('Files Orign (INPUT): ' + files_orign)
	logger.info('Files Destination (OUTPUT): ' + files_destination)
	logger.info('Folders: '+ folders)
	logger.info('Show datetime in prefix format: ' +  now.strftime(folders))
	logger.info('Files Prefix: '+ files_prefix)
	logger.debug('Show datetime in prefix format: ' + now.strftime(files_prefix))

	# Reference: https://stackoverflow.com/questions/2909975/python-list-directory-subdirectory-and-files#2909998
	counter_quantity_images = 0
	for path, subdirs, files in os.walk(files_orign):
		for file_name in files:
			#image_file = os.path.join(path, file_name)
			image_file = str(pathlib.PurePath(path, file_name))
			if (file_name.endswith(IMAGE_EXTENSIONS)):
				counter_quantity_images = counter_quantity_images + 1
				if ((batch_quantity_images == 0) or (counter_quantity_images <= batch_quantity_images)):
					logger.info('--- Processando imagem: ' + str(counter_quantity_images) + ' de no máximo ' + str(batch_quantity_images) + ' ---')
					logger.info('Image: ' + image_file)

					dir_image_year = '0000'
					dir_image_month = '00'
					dir_image_sufix = 'others'
					exif_utilizado = ''
					date_dir_destination = datetime.date(int('1977'), int('08'), int('17'))
					dir_destination = date_dir_destination.strftime(folders)
					new_file_name = ''

					#----------------------------------------------------------------------#
					# Reading filesystem date information:
					# Reference: https://stackoverflow.com/questions/237079/how-to-get-file-creation-and-modification-date-times
					# Reference: https://www.geeksforgeeks.org/how-to-get-file-creation-and-modification-date-or-time-in-python/
					# Reference: https://docs.python.org/3/library/datetime.html
					# Reference: https://pynative.com/python-datetime-format-strftime/
					# Reference: https://code-paper.com/python/examples-python-datetime-convert-float-to-date

					image_file_creation_date = 0
					if platform.system() == 'Windows':
						image_file_creation_date = min(os.path.getctime(image_file), os.path.getctime(image_file))
					else:
						stats = os.stat(image_file)
						try:
							image_file_creation_date = stats.st_ctime
						except AttributeError:
							image_file_creation_date = min(stats.st_birthtime, stats.st_mtime, stats.st_ctime)

					if (image_file_creation_date != 0):
						date_dir_destination  = datetime.datetime.fromtimestamp(image_file_creation_date)
						new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name[0:50]
						dir_destination = date_dir_destination.strftime(folders)
						logger.debug('Filesystem timestamp: ' + str(image_file_creation_date))
						logger.debug('Filesystem date: ' + str(date_dir_destination))
					else:
						logger.debug('No date from filesystem!')

					#----------------------------------------------------------------------#
					# Reading date information from file name using RegEx:
					# Reference: https://github.com/excellentsport/picOrganizer
					# Reference: https://regexland.com/regex-dates/

					# YYYY-MM-DD-HH-MM-SS:
					datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])([-_])(0[1-9]|1[0-2])([-_])(0[1-9]|[1-2][0-9]|3[0-1])([-_])([0-1][0-9]|2[0-4])([-_])([0-5][0-9])([-_])([0-5][0-9])')
					regex_match = datetime_regex.search(image_file)
					if not(regex_match is None):
						dir_image_second = regex_match.group()[17:19]
						dir_image_minute = regex_match.group()[14:16]
						dir_image_hour = regex_match.group()[11:13]
						dir_image_day = regex_match.group()[8:10]
						dir_image_month = regex_match.group()[5:7]
						dir_image_year = regex_match.group()[0:4]
						#logger.info('lilas - RegEx: ' + regex_match.group() + ', Year: '+ dir_image_year + ', Month: ' + dir_image_month + ', Day: ' + dir_image_day)
						date_dir_destination = datetime.datetime(int(dir_image_year), int(dir_image_month), int(dir_image_day), int(dir_image_hour), int(dir_image_minute), int(dir_image_second))
						#logger.info('lilas - RegEx: ' + regex_match.group() + ', Year: '+ dir_image_year + ', Month: ' + dir_image_month + ', Day: ' + dir_image_day)
					else:
						# YYYYMMDD_HHMMSS:
						datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])(0[1-9]|1[0-2])(0[1-9]|[1-2][0-9]|3[0-1])([-_])([0-1][0-9]|2[0-4])([0-5][0-9])([0-5][0-9])')
						regex_match = datetime_regex.search(image_file)
						if not(regex_match is None):
							dir_image_second = regex_match.group()[13:15]
							dir_image_minute = regex_match.group()[11:13]
							dir_image_hour = regex_match.group()[9:11]
							dir_image_day = regex_match.group()[6:8]
							dir_image_month = regex_match.group()[4:6]
							dir_image_year = regex_match.group()[0:4]
							date_dir_destination = datetime.datetime(int(dir_image_year), int(dir_image_month), int(dir_image_day), int(dir_image_hour), int(dir_image_minute), int(dir_image_second))
							#logger.info('rosa - RegEx: ' + regex_match.group() + ', Year: '+ dir_image_year + ', Month: ' + dir_image_month + ', Day: ' + dir_image_day)
						else:
							# YYYYMMDD, YYYY_MM_DD, YYYY-MM-DD:
							datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])([-_]?)(0[1-9]|1[0-2])([-_]?)(0[1-9]|[1-2][0-9]|3[0-1])')
							regex_match = datetime_regex.search(image_file)
							if not(regex_match is None):
								dir_image_day = regex_match.group()[-2:]
								if (len(regex_match.group())>8):
									dir_image_month = regex_match.group()[5:7]
								else:
									dir_image_month = regex_match.group()[4:6]
								dir_image_year = regex_match.group()[0:4]
								date_dir_destination = datetime.date(int(dir_image_year), int(dir_image_month), int(dir_image_day))
								#logger.info('verde - RegEx: ' + regex_match.group() + ', Year: '+ dir_image_year + ', Month: ' + dir_image_month + ', Day: ' + dir_image_day)
							else:
								# DDMMYYYY, DD_MM_YYYY, DD-MM-YYYY:
								datetime_regex = re.compile(r'(0[1-9]|[1-2][0-9]|3[0-1])([-_]?)(0[1-9]|1[0-2])([-_]?)(19[7-9][0-9]|20[0-2][0-9])')
								regex_match = datetime_regex.search(image_file)
								if not(regex_match is None):
									dir_image_day = regex_match.group()[0:2]
									if (len(regex_match.group())>8):
										dir_image_month = regex_match.group()[2:4]
									else:
										dir_image_month = regex_match.group()[3:5]
									dir_image_year = regex_match.group()[-4]
									date_dir_destination = datetime.date(int(dir_image_year), int(dir_image_month), int(dir_image_day))
									#logger.info('azul - RegEx: ' + regex_match.group() + ', Year: '+ dir_image_year + ', Month: ' + dir_image_month + ', Day: ' + dir_image_day)
					if ( dir_image_year != '0000'):
						new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name[0:50]
						dir_destination = date_dir_destination.strftime(folders)
						logger.debug('Filename date: ' + str(date_dir_destination))
					else:
						logger.debug('No date from filename!')

					#----------------------------------------------------------------------#
					# Reading EXIF date information:
					# Reference: https://orthallelous.wordpress.com/2015/04/19/extracting-date-and-time-from-images-with-python/
					# Reference: https://github.com/vitords/sort-images/blob/master/sort_images.py
					try:
						image = Image.open(image_file)
						exif_dict = piexif.load(image.info['exif'])
						#logger.debug('EXIF loaded successfuly.')
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
						new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name[0:50]
						logger.debug('Filename from EXIF ('+ exif_utilizado +'): ' + str(date_dir_destination))
					else:
						logger.debug('No date from EXIF!')

					#----------------------------------------------------------------------#
					# Reading Geodata information:
					# Reference: https://towardsdatascience.com/grabbing-geodata-from-your-photos-library-using-python-60eb0462e147
					geodata = gpsphoto.getGPSData(image_file)
					logger.debug('GeoData: ' + str(geodata))

					#----------------------------------------------------------------------#
					# Generating folder sufix:
					# Reference: https://pythonguides.com/python-find-substring-in-string/
					# Reference: https://flaviocopes.com/python-get-file-details/

					image_file_size = 0
					if platform.system() == 'Windows':
						image_file_size = os.path.getsize(image_file)
					else:
						stats = os.stat(image_file)
						image_file_size = stats.st_size
					if (image_file_size < min_size_escape_low_resolution):
						dir_image_sufix = 'low_resolution'

					if ('insta' in image_file.lower()):
						dir_image_sufix = 'social_media'
					if (('instagram' in image_file.lower()) or ('facebook' in image_file.lower())):
						dir_image_sufix = 'social_media'
					if (('message' in image_file.lower()) or ('telegram' in image_file.lower()) or ('whats' in image_file.lower()) or ('instant' in image_file.lower())):
						dir_image_sufix = 'instant_messages'
					if (('screen' in image_file.lower()) or ('capture' in image_file.lower())):
						dir_image_sufix = 'screen_capture'

					logger.debug('Sufixo encontrado no nome: ' + dir_image_sufix)

					if (generate_folder_sufix):
						new_file_dir = files_destination + dir_destination + '-'  + dir_image_sufix + '\\'
					else:
						new_file_dir = files_destination + dir_destination + '\\'

					logger.info('New file and folder: ' + new_file_dir + new_file_name)

					if not os.path.exists(new_file_dir):
						os.makedirs(new_file_dir)

					shutil.move(image_file, new_file_dir + new_file_name)
					#os.rename(image_file, new_file_dir + file_name)
					logger.info('Was moved.')

				else:
					logger.debug('Batch limt: ' + str(batch_quantity_images) + ' - Ignoring file ' + str(image_file))
			else:
				logger.debug('Extension - Ignoring file ' + str(image_file))

	sys.exit(0)

#----------------------------------------------------------------------------------------------#
if __name__ == '__main__':
	main()