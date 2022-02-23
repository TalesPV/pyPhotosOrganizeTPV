import os
from sqlite3 import IntegrityError
import sys
import pathlib
import time
# Reference:  https://www.codevscolor.com/python-print-date-time-hour-minute
# Reference: https://www.programiz.com/python-programming/datetime
# Reference: https://www.tutorialspoint.com/How-to-print-current-date-and-time-using-Python
import datetime
import argparse
# Reference: https://pypi.org/project/coloredlogs/
# Reference: https://coloredlogs.readthedocs.io/en/latest/readme.html
# Reference: https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
import coloredlogs
# Reference: https://www.geeksforgeeks.org/logging-in-python/
import logging

# Basic References:
# https://www.youtube.com/watch?v=--_K4G3HCcI
# https://blog.gunderson.tech/26307/using-virtual-environment-requirements-txt-with-python

parser = argparse.ArgumentParser(description='Script options parser.')

parser.add_argument('-o', '--files_orign', type=str, required=False, default='.\\resources\\input_files\\')
parser.add_argument('-d', '--files_destination', type=str, required=False, default='.\\resources\\output_files\\')
parser.add_argument('-f', '--folders', type=str, required=False, default='%Y_%m_%b')
parser.add_argument('-p', '--files_prefix', type=str, required=False, default='%Y_%m_%d_%Hh%Mm%Ss')
parser.add_argument('-q', '--batch_quantity_images', type=int, required=False, default=0)
# min_width_escape_low_resolution
# min_size_escape_low_resolution
# min_year_discart_date
# generate_folder_sufix : exif, screen, instante_message, low_resolution, file_system, name_date, others
# rename_file

args = parser.parse_args()

# Define what image and video file extensions to search for:
IMAGE_EXTENSIONS = ('.png', '.jpeg', '.jpg', '.gif')
VIDEOS_EXTENSIONS = ('.mov', 'mp4')


#----------------------------------------------------------------------------------------------#
def get_image_reference_date(image_file):
	image_reference_date = datetime.datetime.now();
	return image_reference_date;

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
		level='DEBUG', 
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

	files_orign = 'D:\\dropbox\\fotos-tpv\\_organizar\\'
	batch_quantity_images = 10

	logger = log_inicialization()

	logger.info('<< pyPhotosOrganizeTPV >>')

	logger.info('Starting script...')

	logger.info('Arguments:')
	logger.info('Files Orign (INPUT): ' + files_orign)
	logger.info('Files Destination (OUTPUT): ' + files_destination)
	logger.info('Folders: '+ folders)
	logger.info('Show datetime in prefix format: ' + datetime.datetime.strftime(datetime.datetime.now() , folders))
	logger.info('Files Prefix: '+ files_prefix)
	logger.debug('Show datetime in prefix format: ' + datetime.datetime.strftime(datetime.datetime.now() , files_prefix))

	# Reference: https://stackoverflow.com/questions/2909975/python-list-directory-subdirectory-and-files#2909998
	counter_quantity_images = 0
	for path, subdirs, files in os.walk(files_orign):
		for file_name in files:
			image_file = pathlib.PurePath(path, file_name)
			if file_name.endswith(IMAGE_EXTENSIONS):
				counter_quantity_images = counter_quantity_images + 1
				if ((batch_quantity_images == 0) or (counter_quantity_images <= batch_quantity_images)):
					logger.debug(str(image_file))
					#logger.debug(os.path.join(path, file_name))
					get_image_reference_date(image_file)
				else:
					logger.info('Batch limt: ' + str(batch_quantity_images) + ' - Ignoring file ' + str(image_file))
			else:
				logger.info('Extension - Ignoring file ' + str(image_file))

	# TO_DO: 
	# https://github.com/excellentsport/picOrganizer
	# https://orthallelous.wordpress.com/2015/04/19/extracting-date-and-time-from-images-with-python/
	# https://www.reddit.com/r/learnpython/comments/d2i15b/i_wrote_a_script_to_organize_image_and_video/
	# https://towardsdatascience.com/grabbing-geodata-from-your-photos-library-using-python-60eb0462e147
	# https://www.geeksforgeeks.org/working-images-python/
	# https://towardsdatascience.com/automate-renaming-and-organizing-files-with-python-89da6560fe42
	# https://github.com/vitords/sort-images

	sys.exit(0)

#----------------------------------------------------------------------------------------------#
if __name__ == '__main__':
	main()