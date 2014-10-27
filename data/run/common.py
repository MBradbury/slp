import os
import fnmatch


class RunSimulationsCommon:
    optimisations = '-OO'
    
    def __init__(self, driver, results_directory, skip_completed_simulations=True):
        self.driver = driver
        self.results_directory = results_directory
        self.skip_completed_simulations = skip_completed_simulations

        if not os.path.exists(self.results_directory):
            raise Exception("{} is not a directory".format(self.results_directory))

    def _check_existing_results(self):
        self.existing_results = {}

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        for infile in files:
            with open(os.path.join(self.results_directory, infile)) as f:
            
                fileopts = {}

                seen_hash = False
                results_count = 0
            
                for line in f:
                    if '=' in line:
                        # We are reading the options so record them
                        opt = line.split('=')

                        fileopts[opt[0].strip()] = opt[1].strip()
                        
                    elif '#' in line:
                        seen_hash = True

                    # Count result lines
                    if seen_hash:
                        if ',' in line:
                            results_count += 1

                
                if len(fileopts) != 0:
                    self.existing_results[(
                        fileopts['Network Size'],
                        fileopts['Source Period'],
                        fileopts['Configuration'],
                        fileopts['Network Type']
                        )] = (int(fileopts['Jobs']), results_count)

    def _already_processed(self, size, source_rate, configuration, type, repeats):
        if not self.skip_completed_simulations:
            return False

        key = (str(size), str(int(1.0/source_rate)), str(configuration), str(type))

        if key not in self.existing_results:
            return False

        # Check that more than enough jobs were done
        (jobs, results) = self.existing_results[key]

        # If the number of jobs recorded in the file and the number of jobs
        # actually executed are greater than or equal to the number of jobs
        # requested then everything is okay.
        return jobs >= repeats and results >= repeats
