import numpy as np
import mne
import matplotlib.pyplot as plt
from operator import itemgetter
from loguru import logger

class Evaluation_Framework:
    def __init__(self, FACET):
        self._eeg_eval_dict_list = []
        self._FACET = FACET
        return

    def add_to_evaluate(self, eeg, start_time=None, end_time=None, name=None):
        """
        Add EEG data to the evaluation list.

        Args:
            eeg (dict): Dictionary containing EEG data.
            start_time (float, optional): Start time of the data to be evaluated. If not provided, it defaults to the start time of the first trigger.
            end_time (float, optional): End time of the data to be evaluated. If not provided, it defaults to the end time of the last trigger section.
            name (str, optional): Name of the evaluation data. Defaults to None.

        Returns:
            None
        """
        if not end_time:
            end_time = eeg.time_last_trigger_end if eeg.time_last_trigger_end else eeg.data_time_end
        if not start_time:
            start_time = eeg.time_first_trigger_start if eeg.time_first_trigger_start else eeg.data_time_start
        raw = eeg.mne_raw.copy()
        logger.debug("Channels that will be evaluated: "+ str(raw.ch_names))

        eeg_channels = mne.pick_types(
            raw.info, meg=False, eeg=True, stim=False, eog=False, exclude="bads"
        )
        channels_to_keep = [raw.ch_names[i] for i in eeg_channels[:]]
        cropped_mne_raw = self._crop(raw=eeg.mne_raw, tmin=start_time, tmax=end_time).pick(channels_to_keep)
        ref_mne_raw = self._crop(raw=eeg.mne_raw, tmin=0, tmax=start_time).pick(channels_to_keep)
        artifact_raw_reference_raw_dict = {"eeg": eeg, "raw": cropped_mne_raw, "ref": ref_mne_raw, "raw_orig": eeg.mne_raw_orig, "name": name}

        self._eeg_eval_dict_list.append(artifact_raw_reference_raw_dict)

        return

    def _crop(self, raw,  tmin, tmax):
        """
        Crop the raw data to the specified time window.
        
        Args:
            raw (mne.io.Raw): Raw data to be cropped.
            tmin (float): Start time of the crop.
            tmax (float): End time of the crop.

        Returns:
            mne.io.Raw: Cropped raw data.
        """
        return raw.copy().crop(tmin=tmin, tmax=tmax)

    def _cutout(self,raw, tmin, tmax):
        """
        Cut out the specified time window from the raw data.

        Args:
            raw (mne.io.Raw): Raw data to be cut out.
            tmin (float): Start time of the cut out.
            tmax (float): End time of the cut out.

        Returns:
            mne.io.Raw: Cut out raw data.
        """
        first_part = raw.copy().crop(tmax=tmin)

        second_part = raw.copy().crop(tmin=tmax)

        first_part.append(second_part)
        return first_part
    
    def evaluate(self, plot=True, measures=[]):
        """
        Evaluate the EEG datasets and calculate the specified measures.

        Args:
            plot (bool, optional): If True, the results will be plotted. Defaults to True.
            measures (list, optional): List of measures to be calculated. Defaults to [].

        Returns:
            list: A list of dictionaries containing the results of the evaluation.
        """
        results=[]
        if "SNR" in measures:
            results.append({"Measure":"SNR","Values":self.evaluate_SNR(),"Unit":"dB"})
        if "RMS" in measures:
            results.append({"Measure":"RMS Uncorrected to Corrected","Values":self.evaluate_RMS_corrected_ratio(),"Unit":"Ratio"})
        if "RMS2" in measures:
            results.append({"Measure":"RMS Corrected to Unimpaired","Values":self.evaluate_RMS_residual_ratio(),"Unit":"Ratio"})
        if "MEDIAN" in measures:
            results.append({"Measure":"MEDIAN","Values":self.calculate_median_imaging_artifact(),"Unit":"V"})
        if plot:
            self.plot(results)
        return results
    # Plot all results with matplotlib
    def plot(self, results):
        """
        Plot the results of the evaluation.

        Args:
            results (list): List of dictionaries containing the results of the evaluation.

        Returns:
            int: 0 if successful.
        """

        # Determine the number of subplots based on the number of measures
        num_subplots = len(results)

        # Create subplots with 1 row and as many columns as there are measures
        fig, axs = plt.subplots(1, num_subplots, figsize=(5 * num_subplots, 5))

        # If there is only one measure, axs is not returned as a list
        if num_subplots == 1:
            axs = [axs]

        # Fill each subplot
        for ax, result in zip(axs, results):
            bars = ax.bar(range(len(result["Values"])), result["Values"])
            ax.set_title(result["Measure"])
            ax.set_ylabel(result["Measure"] + ' in ' + (result['Unit'] if result['Unit'] else ''))
            x_labels = [eval_eeg_ref_dict["name"] for eval_eeg_ref_dict in self._eeg_eval_dict_list]  # Replace with your labels
            ax.set_xticks(range(len(result["Values"])))
            ax.set_xticklabels(x_labels, rotation=45)

        # Display the entire window with all subplots
        plt.tight_layout()  # Used to ensure that the subplots do not overlap
        plt.show()

        return 0
    def evaluate_RMS_corrected_ratio(self):
        """
        Calculates the RMS of the EEG datasets.

        Returns:
            results (list): A list of RMS values for each dataset.
        """
        if not self._eeg_eval_dict_list:
            logger.error("Please set at least one EEG dataset and crop the EEG to evaluate before calculating RMS.")
            return
        results = []
        for mnedict in self._eeg_eval_dict_list:
            # Extracting the data
            data_corrected = mnedict["raw"].get_data()
            data_uncorrected = mnedict["raw_orig"].get_data()

            #TODO: Bugfix for different number of channels
            if data_corrected.shape[0] != data_uncorrected.shape[0]:
                data_uncorrected = data_uncorrected[:data_corrected.shape[0],:]

            # Calculate RMS
            rms_corrected = np.sqrt(np.mean(data_corrected**2, axis=1))
            rms_uncorrected = np.sqrt(np.mean(data_uncorrected**2, axis=1))

            # Calculate Ratio
            rms = rms_uncorrected / rms_corrected
            np.median(rms)
            results.append(np.median(rms))        

        return results
    def evaluate_RMS_residual_ratio(self):
        """
        Calculates the RMS of the EEG datasets.

        Returns:
            results (list): A list of RMS values for each dataset.
        """
        if not self._eeg_eval_dict_list:
            logger.error("Please set at least one EEG dataset and crop the EEG to evaluate before calculating RMS.")
            return
        results = []
        for mnedict in self._eeg_eval_dict_list:
            # Extracting the data
            data_corrected = mnedict["raw"].get_data()
            data_ref = mnedict["ref"].get_data()

            # Calculate RMS
            rms_corrected = np.sqrt(np.mean(data_corrected**2, axis=1))
            rms_ref = np.sqrt(np.mean(data_ref**2, axis=1))

            # Calculate Ratio
            rms = rms_corrected / rms_ref
            np.median(rms)
            results.append(np.median(rms))        

        return results
    def calculate_median_imaging_artifact(self):
        """
        Calculates the Median Imaging Artifact for each EEG dataset in eeg_list.

        Returns:
            list: A list of median imaging artifact values for each dataset.
        """
        if not hasattr(self, '_eeg_eval_dict_list') or not self._eeg_eval_dict_list:
            logger.error("eeg_list is not set or empty.")
            return

        results = []

        for mne_dict in self._eeg_eval_dict_list:
            _eeg = mne_dict['eeg']
            if _eeg.mne_raw is None:
                logger.error("EEG dataset is not set for this mne_dict.")
                continue

            # Create epochs around the artifact triggers
            events = np.column_stack((_eeg.loaded_triggers, np.zeros_like(_eeg.loaded_triggers), np.ones_like(_eeg.loaded_triggers)))
            tmin = _eeg.get_tmin()  # Start time before the event
            tmax = _eeg.get_tmax()  # End time after the event
            baseline = None  # No baseline correction
            picks = mne.pick_types(_eeg.mne_raw.info, meg=False, eeg=True, stim=False, eog=False, exclude='bads')

            epochs = mne.Epochs(_eeg.mne_raw, events = events, tmin = tmin, tmax = tmax, proj=True,reject=None, picks=picks, baseline=baseline, preload=True)
            # Calculate the peak-to-peak value for each epoch and channel
            p2p_values_per_epoch = [np.ptp(epoch, axis=1) for epoch in epochs.get_data()]

            # Calculate the mean peak-to-peak value per epoch across all channels
            mean_p2p_per_epoch = [np.mean(epoch_p2p) for epoch_p2p in p2p_values_per_epoch]

            # Calculate the median of these mean values
            vmed = np.median(mean_p2p_per_epoch)

            results.append(vmed)

        return results
    def evaluate_SNR(self):
        """
        Calculates the SNR of the EEG datasets.

        Returns:
            results (list): A list of SNR values for each dataset.
        """
        if not self._eeg_eval_dict_list:
            logger.error("Please set both EEG datasets and crop the EEG to evaluate before calculating SNR.")
            return
        results = []
        for mnedict in self._eeg_eval_dict_list:
            # Extracting the data
            data_to_evaluate = mnedict["raw"].get_data()
            data_reference = mnedict["ref"].get_data()

            # Calculate power of the signal
            power_corrected = np.var(data_to_evaluate, axis=1)
            power_without = np.var(data_reference, axis=1)

            # Calculate power of the residual (noise)
            power_residual = power_corrected - power_without

            # Calculate SNR
            snr = np.abs(power_without / power_residual)

            results.append(np.median(snr))        

        return results