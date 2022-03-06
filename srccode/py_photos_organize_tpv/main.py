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

from xmlrpc.client import DateTime
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

args = parser.parse_args()

# Version:
PROJETCT_VERSION = '1.0.0.20220305202600'

# Define extensions to be processed and to obtain metadata:
IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.gif', '.bmp', '.tif')
VIDEO_EXTENSIONS = ('.mov', '.mp4', '.avi', '.mov')
MSOFFICE_EXTENSIONS = ('.doc', '.docx', '.xls', '.xlsx')
OTHER_EXTENSIONS = ('.pdf', )
ALL_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS + MSOFFICE_EXTENSIONS + OTHER_EXTENSIONS


#----------------------------------------------------------------------------------------------#
# Reference: https://pypi.org/project/coloredlogs/
def log_inicialization() -> logging.Logger:

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

	filesystem_datetime = None
	if (platform.system() == 'Windows'):
		try:
			filesystem_datetime = min(os.path.getctime(absolut_file_name), os.path.getatime(absolut_file_name), os.path.getmtime(absolut_file_name))
		except Exception as e:
			logger.error(str(e))
	else:
		try:
			stats = os.stat(absolut_file_name)
			filesystem_datetime = min(stats.st_birthtime, stats.st_mtime, stats.st_ctime)
		except Exception as e:
			logger.error(str(e))

	if (filesystem_datetime != None):
		datetime_filesystem = datetime.datetime.fromtimestamp(filesystem_datetime)
	else:
		datetime_filesystem = None

	return datetime_filesystem


#----------------------------------------------------------------------------------------------#
# Reference: https://datagy.io/python-return-multiple-values/

#----------------------------------------------------------------------------------------------#
# Reference: https://stackoverflow.com/questions/2909975/python-list-directory-subdirectory-and-files#2909998
# Reference: https://docs.python.org/3/library/datetime.html
# Reference: https://pynative.com/python-datetime-format-strftime/
# Reference: https://code-paper.com/python/examples-python-datetime-convert-float-to-date
def main():

	# Obtain parameters from the system call:
	files_orign = args.files_orign
	files_destination = args.files_destination
	folders = args.folders
	files_prefix = args.files_prefix
	batch_quantity_files = args.batch_quantity_files
	exif_min_year_discart_date = args.exif_min_year_discart_date
	generate_folder_sufix = args.generate_folder_sufix
	min_size_escape_low_resolution = args.min_size_escape_low_resolution
	rename_file = args.rename_file

	logger = log_inicialization()

	logger.info('---------- << pyPhotosOrganizeTPV >> ----------')

	logger.info('Starting script version '+ PROJETCT_VERSION +'...')

	now = datetime.datetime.now()
	logger.debug('------ Arguments / Parameters:')
	logger.debug('Files Orign (INPUT): ' + files_orign)
	logger.debug('Files Destination (OUTPUT): ' + files_destination)
	logger.debug('Folders mask: '+ folders)
	logger.debug('Files prefix mask: '+ files_prefix)
	
	logger.debug('------ Test:')
	logger.debug('Showing datetime in folder format: ' +  now.strftime(folders))
	logger.debug('Showing datetime in prefix format: ' + now.strftime(files_prefix))

	counter_files_processed = 0
	counter_files_on_destination = 0

	file_name = ''
	file_name_absolut = ''

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
					logger.info('Absolut file name: ' + file_name_absolut)


					'''
					dir_image_year = '0000'
					dir_image_month = '00'
					dir_image_sufix = 'others'
					date_dir_destination = datetime.date(int('1977'), int('08'), int('17'))
					dir_destination = date_dir_destination.strftime(folders)
					new_file_name = ''
					'''
					exif_utilizado = ''

					#----------------------------------------------------------------------#
					file_datetime_stamp = None
					filesystem_file_datetime = get_filesystem_datetime(logger, file_name_absolut)

					if (filesystem_file_datetime != None):
						logger.debug('Filesystem datetime stamp: ' + str(filesystem_file_datetime))
						if ((file_datetime_stamp == None) or (file_datetime_stamp > filesystem_file_datetime)):
							file_datetime_stamp = filesystem_file_datetime
					else:
						logger.debug('No datetime from filesystem!')

					if (file_datetime_stamp != None):
						dir_destination = file_datetime_stamp.strftime(folders)
						if (rename_file == False):
							new_file_name = file_name
						else:
							if (len(file_name)>100):
								new_file_name = file_datetime_stamp.strftime(files_prefix) + '-' + file_name[-100:]
							else:
								new_file_name = file_datetime_stamp.strftime(files_prefix) + '-' + file_name

					#----------------------------------------------------------------------#
					# Reading date information from file name using RegEx:
					# Reference: https://github.com/excellentsport/picOrganizer
					# Reference: https://regexland.com/regex-dates/

					# YYYY-MM-DD-HH-MM-SS:
					datetime_regex = re.compile(r'(19[7-9][0-9]|20[0-2][0-9])([-_])(0[1-9]|1[0-2])([-_])(0[1-9]|[1-2][0-9]|3[0-1])([-_])([0-1][0-9]|2[0-4])([-_])([0-5][0-9])([-_])([0-5][0-9])')
					regex_match = datetime_regex.search(file_name_absolut)
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
						regex_match = datetime_regex.search(file_name_absolut)
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
							regex_match = datetime_regex.search(file_name_absolut)
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
								regex_match = datetime_regex.search(file_name_absolut)
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
						dir_destination = date_dir_destination.strftime(folders)
						if (rename_file == False):
							new_file_name = file_name
						else:
							if (len(file_name)>100):
								new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name[-100:]
							else:
								new_file_name = date_dir_destination.strftime(files_prefix) + '-' + file_name
						logger.debug('File name date: ' + str(date_dir_destination))
					else:
						logger.debug('No date from file name!')

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

					if os.path.exists(complete_path_new_file):
						counter_files_on_destination = counter_files_on_destination + 1
						try:
							logger.debug('Tamanho origem: ' + str(os.path.getsize(file_name_absolut)))
							logger.debug('Tamanho destino: ' + str(os.path.getsize(complete_path_new_file)))
							if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
								try:
									os.unlink(file_name_absolut)
									arquivo_movido = True
								except WindowsError as e:
									logger.error("The error thrown was {e}".format(e=e))
									'''
									if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
										logger.info('Esperando 10s...')
										time.sleep(1)
										try:
											os.remove(file_name_absolut)
											arquivo_movido = True
										except WindowsError as e:
											logger.error("The error thrown was {e}".format(e=e))
									'''
						except WindowsError as e:
							logger.error("The error thrown was {e}".format(e=e))

					if (arquivo_movido == False):
						try:
							shutil.move(file_name_absolut, complete_path_new_file)
							arquivo_movido = True
							logger.info('Image was moved.')
						except WindowsError as e:
							logger.error("There was an error copying {picture} to {target}".format(picture=file_name_absolut,target=complete_path_new_file))
							logger.error("The error thrown was {e}".format(e=e))
						except PermissionError:
							logger.error('Error trying to rename file.')

					if (arquivo_movido == False):
						try:
							os.rename(file_name_absolut, complete_path_new_file)
							arquivo_movido = True
							logger.info('Image was renamed.')
						except PermissionError:
							logger.error('Error trying to rename file.')

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

					if (arquivo_movido == False):
						logger.debug('Tamanho origem: ' + str(os.path.getsize(file_name_absolut)))
						logger.debug('Tamanho destino: ' + str(os.path.getsize(complete_path_new_file)))
						if (os.path.getsize(file_name_absolut) == os.path.getsize(complete_path_new_file)):
							try:
								os.remove(file_name_absolut)
							except WindowsError as e:
								logger.error("The error thrown was {e}".format(e=e))
							except PermissionError:
								logger.error('Error trying to rename file.')

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