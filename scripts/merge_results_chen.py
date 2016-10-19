import glob
import os
import re
import sys

#define the maximum lines of results(configuration header not include) 
max_line = 500

if len(sys.argv) != 2:
	raise RuntimeError("No algorithm name provided!")

results_dir = os.path.join(os.getcwd(), 'results', list(sys.argv)[-1])
merge_dir = os.path.join(results_dir,'merged_results')

if not os.path.exists(merge_dir):
    os.makedirs(merge_dir)

os.chdir(results_dir)

for filename in glob.glob('*.txt'):

	parameter_check = False
	config_finish = False
	maximum_result_lines = 0
	parameters = []
	file_dir = os.path.join(merge_dir, filename)

	#gather all parameters from the header of result files.
	with open (filename) as currentfile:
		for line in currentfile:
			line_first_word = re.split('=|\||:',line)[0]
			
			if parameter_check == False:
				parameters.append(line_first_word)
			else:
				pass

			if line_first_word == '#Seed':
				parameter_check = True
		

	with open (filename) as oldfile, open(file_dir, 'w') as newfile:
		for line in oldfile:
			if maximum_result_lines < max_line + len(parameters):
				if any(word in line for word in parameters) and config_finish == True:
					pass
				elif '#Seed' in line:
					newfile.write(line)
					config_finish = True
				else:
					newfile.write(line)
			else:
				pass
			maximum_result_lines += 1