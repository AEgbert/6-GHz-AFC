#    Copyright 2023 6 GHz AFC Project Authors. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
"""Conversion library and top-level script for translating AFC responses to a response mask"""

from decimal import Decimal

# Handle python search path when running script as main
if __name__ == '__main__':
  from os import sys, path
  sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import available_spectrum_inquiry_response as afc_resp
import expected_inquiry_response as exp_resp
from response_mask_validator import ResponseMaskValidator
from response_validator import InquiryResponseValidator
from interface_common import JSONEncoderSDI, ResponseCode

## Conversion functions
def exp_range_from(nominal_value, margins: dict=None, limits: dict=None):
  """Generates an ExpectedPowerRange object from a nominal value and optional margins and range
  limits. Limits are computed according to:
  upperBound = min(nominal_value + margins['upper'], limits['upper'])
  lowerBound = max(nominal_value - margins['lower'], limits['lower'])

  The nominal value will also be coerced to be within the specified limits, prior to bound
  calculation.

  Default margins are: 0 for upper, inf for lower
  Default limits are: inf for upper, -inf for lower

  Parameters:
    nominal_value (numeric): Key value representing the range's anchor point
    margins (dict): Upper and lower margins on the nominal value used to establish
                    upperBound and lowerBound. To use default margins, provide no margins argument
                    or exclude the 'upper' or 'lower' keys.
    limits (dict): Upper and lower limits on the generated upperBound and lowerBound vals
                   To use default limits, provide no limits argument or exclude the 'upper' or
                   'lower' keys.

  Returns:
    Generated ExpectedPowerRange object"""
  # Using Decimal type to avoid extra decimal places that come from default floating-point
  # arithmetic. Long-term, may be preferable to convert full SDI implementation to use
  # Decimal type for power values across the board and load/dump to/from JSON/TOML as Decimal
  # directly

  # Define default margins and limits
  def_margins = {'upper': Decimal(0), 'lower': Decimal('inf')}
  def_limits = {'upper': Decimal('inf'), 'lower': Decimal('-inf')}

  # Select default margins and limits as necessary
  if margins is not None:
    # To get user-provided values as Decimal type without inheriting the floating-point
    # approximation, ask Python for the string form (removing the extra decimal places from
    # the approximation) and then convert to Decimal type
    margin_upper = Decimal(str(margins.get('upper', def_margins['upper'])))
    margin_lower = Decimal(str(margins.get('lower', def_margins['lower'])))
  else:
    (margin_upper, margin_lower) = (def_margins['upper'], def_margins['lower'])

  if limits is not None:
    limit_upper = limits.get('upper', def_limits['upper'])
    limit_lower = limits.get('lower', def_limits['lower'])
  else:
    (limit_upper, limit_lower) = (def_limits['upper'], def_limits['lower'])

  # Coerce nominal_value to be within the specified limits
  # Convert to Decimal in the same way as the provided margins
  nominal_value = Decimal(str(sorted([limit_lower, nominal_value, limit_upper])[1]))

  # Compute bounds and convert result back to float (later serialization should avoid outputting
  # extra decimal places from floating-point approximation)
  upper_bound = float(nominal_value + margin_upper)
  lower_bound = float(nominal_value - margin_lower)

  return exp_resp.ExpectedPowerRange(min(upper_bound, limit_upper),
                                     float(nominal_value),
                                     max(lower_bound, limit_lower))

def exp_freq_info_from(avail_info: afc_resp.AvailableFrequencyInfo, **kwargs):
  """Converts an AvailableFrequencyInfo to an ExpectedAvailableFrequencyInfo object according to
  any provided ExpectedPowerRange rule modifiers.

  Parameters:
    avail_info (AvailableFrequencyInfo): Original frequency info object for conversion
    **kwargs: Modifiers for ExpectedPowerRange conversion
              (see exp_range_from() parameters for details)

  Returns:
    Converted ExpectedAvailableFrequencyInfo object"""
  return exp_resp.ExpectedAvailableFrequencyInfo(avail_info.frequencyRange,
                                                 exp_range_from(avail_info.maxPsd, **kwargs))

def exp_chan_info_from(avail_info: afc_resp.AvailableChannelInfo, **kwargs):
  """Converts an AvailableChannelInfo to an ExpectedAvailableChannelInfo object according to
  any provided ExpectedPowerRange rule modifiers.

  Parameters:
    avail_info (AvailableChannelInfo): Original channel info object for conversion
    **kwargs: Modifiers for ExpectedPowerRange conversion
              (see exp_range_from() parameters for details)

  Returns:
    Converted ExpectedAvailableChannelInfo object"""
  return exp_resp.ExpectedAvailableChannelInfo(avail_info.globalOperatingClass,
    avail_info.channelCfi, [exp_range_from(x, **kwargs) for x in avail_info.maxEirp])

def exp_resp_from(resp: afc_resp.AvailableSpectrumInquiryResponse, expect_less_specific_error=True,
                  permit_any_code=False, psd_margins=None, eirp_margins=None, eirp_limits=None,
                  psd_limits=None, exclude_extensions=True, **kwargs):
  """Converts an AvailableSpectrumInquiryResponse to an ExpectedSpectrumInquiryResponse
  object according to any provided conversion modifiers.

  Parameters:
    resp (AvailableSpectrumInquiryResponse): Original response object for conversion
    expect_less_specific_error (bool): Relaxes the expectedResponseCodes to include GENERAL_FAILURE
                                       if the original response code is a more specific error code
                                       (i.e., not SUCCESS or GENERAL_FAILURE)
    permit_any_code (bool): Empties the generated list of explicitly disallowed response codes.
                            The resulting response mask will cause a logged warning in the presence
                            of an error code not in expectedResponseCodes but will not trigger an
                            UNEXPECTED test result.
    exclude_extensions (bool): Do not include any VendorExtensions from resp in the converted mask
    **kwargs: Modifiers for ExpectedPowerRange conversion
              (see exp_range_from() parameters for details)
  Returns:
    Converted ExpectedSpectrumInquiryResponse object"""

  # Handle relaxing error code
  allowed_codes = [resp.response.responseCode]
  if expect_less_specific_error and (resp.response.responseCode not in
                                     [ResponseCode.SUCCESS, ResponseCode.GENERAL_FAILURE]):
    allowed_codes.append(ResponseCode.GENERAL_FAILURE)

  # Handle permitting any code by setting an empty disallowed list
  disallowed_codes = [] if permit_any_code else None

  return exp_resp.ExpectedSpectrumInquiryResponse(
          resp.requestId,
          resp.rulesetId,
          allowed_codes,
          [exp_freq_info_from(x, margins=psd_margins, limits=psd_limits, **kwargs)
                              for x in resp.availableFrequencyInfo],
          [exp_chan_info_from(x, margins=eirp_margins, limits=eirp_limits, **kwargs)
                              for x in resp.availableChannelInfo],
          resp.vendorExtensions if exclude_extensions is False else None,
          disallowed_codes)

def exp_msg_from(msg: afc_resp.AvailableSpectrumInquiryResponseMessage, exclude_extensions=True,
                 **kwargs):
  """Converts an AvailableSpectrumInquiryResponseMessage to an
  ExpectedSpectrumInquiryResponseMessage object according to any provided conversion modifiers.

  Parameters:
    msg (AvailableSpectrumInquiryResponseMessage): Original response message object for conversion
    exclude_extensions (bool): Do not include any VendorExtensions from msg in the converted mask
    **kwargs: Modifiers for conversion to ExpectedSpectrumInquiryResponse and ExpectedPowerRange
              (see exp_range_from() and exp_resp_from() parameters for details)
  Returns:
    Converted ExpectedSpectrumInquiryResponse object"""
  return exp_resp.ExpectedSpectrumInquiryResponseMessage(
          msg.version,
          [exp_resp_from(x, exclude_extensions=exclude_extensions, **kwargs)
            for x in msg.availableSpectrumInquiryResponses],
          msg.vendorExtensions if exclude_extensions is False else None)

## Conversion script main logic
def main():
  """Iterates over provided source response files and generates test harness mask files from the
  responses"""
  ## Parse command line arguments
  parser = ArgumentParser()
  default_cfg_path = path.join(path.dirname(path.dirname(path.abspath(__file__))), 'cfg', 'resp2mask.toml')
  parser.add_argument('--cfg', action='store', default=default_cfg_path,
                      help='Override path to conversion configuration TOML file. '
                          f'Default is "{default_cfg_path}"')
  parser.add_argument('--output_dir', action='store', default='./masks',
                      help='Path to output directory for converted mask file. Default is "./masks"')
  parser.add_argument('-y', '--assume-yes', '--yes', action='store_true', help='If provided, will '
                      'auto answer "yes" to any prompts (overwrites existing files and creates '
                      'missing directories)')
  parser.add_argument('-q', '--quiet', action='store_true', help='Suppress informational messages '
                      '(implies -y) (skipped file messages will still be printed)')
  parser.add_argument('src', action='store', nargs='+', help='Paths to source responses or '
                      'response sets (directories) to convert. Each entry will be saved as a '
                      'single mask file. For directories, all included src files will be merged '
                      'into a single mask.')
  args = parser.parse_args()

  ## Load harness configuration
  try:
    with open(args.cfg, 'rb') as cfg_file:
      mask2resp_cfg = tomli.load(cfg_file)
  except tomli.TOMLDecodeError as ex:
    print('Could not parse TOML in response-to-mask conversion configuration file. '
         f'Exception details: {ex}')
    sys.exit(1)
  except OSError as ex:
    print(f'Could not read response-to-mask conversion configuration. Exception details: {ex}')
    sys.exit(1)

  ## Create validator objects
  resp_validator = InquiryResponseValidator(echo_log=not args.quiet)
  mask_validator = ResponseMaskValidator(echo_log=not args.quiet)

  ## Iterate over all source arguments (response sets or individual responses)
  for src_path in args.src:
    # Treat directories as a response set
    if path.isdir(src_path):
      src_gen_name = path.basename(src_path) + '_mask.json'
      if not args.quiet:
        print(f'{src_path}: Processing response set...')
      # Get all files (not directories) as potential conversion targets
      src_files = []
      with scandir(src_path) as it:
        for entry in it:
          if entry.is_file():
            src_files.append(entry.path)
    else:
      src_files = [src_path]
      src_gen_name = Path(src_path).stem + '_mask.json'

    mask_set = []
    ## Try to convert every file in the response set
    for src_file in src_files:
      ## Open File
      if not args.quiet:
        print(f'{src_file}: Converting...')
      with open(src_file, encoding='utf-8') as fin:
        resp_raw = fin.read()

      ## Parse JSON
      try:
        resp_json = json.loads(resp_raw)
      except Exception as ex:
        print(f'{src_file}: Not valid JSON: {ex}. Skipping...')
        continue

      ## Parse as response message
      try:
        resp_obj = afc_resp.AvailableSpectrumInquiryResponseMessage(**resp_json)
      except Exception as ex:
        print(f'{src_file}: Could not parse as an AFC response: {ex}. Skipping...')
        continue

      ## Validate ingested response--print warning if failed
      if not resp_validator.validate_available_spectrum_inquiry_response_message(resp_obj):
        if not args.quiet:
          print(f'{src_file}: Not a valid response, mask may be incorrect...')

      ## Run conversion
      try:
        mask_obj = exp_msg_from(resp_obj, **mask2resp_cfg)
      except Exception as ex:
        print(f'{src_file}: Failed to convert response to mask: {ex}. Skipping...')
        continue

      ## Validate conversion result--skip file if failed
      if not mask_validator.validate_expected_spectrum_inquiry_response_message(mask_obj):
        print(f'{src_file}: Generated mask is not valid, skipping...')
        continue

      ## Clear disallowedResponseCodes if default behavior was used
      # (ensures current default behavior doesn't override future default behavior at test time)
      if not mask2resp_cfg.get('permit_any_code', False):
        for sub_mask in mask_obj.expectedSpectrumInquiryResponses:
          sub_mask.disallowedResponseCodes = None

      mask_set.append(mask_obj)

    ## Prepare mask set for single mask file
    match len(mask_set):
      case 0:
        print(f'{src_path}: Found no valid responses, skipping...')
        continue
      case 1:
        mask_obj = mask_set[0]
      case _:
        # Merge masks
        mask_obj = mask_set[0]
        for mask in mask_set[1:]:
          if mask_obj.version != mask.version:
            print(f'{src_path}: Responses have different versions, cannot be merged. Skipping...')
            continue
          else:
            mask_obj.expectedSpectrumInquiryResponses.extend(mask.expectedSpectrumInquiryResponses)
            if mask_obj.vendorExtensions is not None:
              mask_obj.vendorExtensions.extend(mask.vendorExtensions)
            else:
              mask_obj.vendorExtensions = mask.vendorExtensions

    ## Determine mask file name
    wfa_id = re.fullmatch(r'REQ-([A-Z]{3})(\d+)',
             mask_obj.expectedSpectrumInquiryResponses[0].requestId)
    if wfa_id:
      # For WFA vectors with multiple responses, derive mask name from folder name
      if len(mask_obj.expectedSpectrumInquiryResponses) > 1:
        mask_file_name = f'AFCS.{path.basename(src_path).replace("_", ".")}_mask.json'
      # For single WFA responses, derive mask name from request ID
      else:
        mask_file_name = '.'.join(['AFCS'] + list(wfa_id.groups())) + '_mask.json'
    # For non-WFA test vectors, derive the filename from the source filename
    else:
      mask_file_name = src_gen_name

    output_path = path.join(args.output_dir, mask_file_name)

    ## Prompt for file issues
    if not (args.assume_yes or args.quiet):
      # Get overwrite permission if needed
      if path.exists(output_path):
        print(f'Output file "{output_path}" already exists! Overwrite it? [y/n]')
        if not _ask_yes_no('overwrite '):
          print(f'{src_path}: Skipping {output_path}...')
          continue
      if not path.exists(args.output_dir):
        # Get permission to make missing directories
        print(f'Output directory "{args.output_dir}" does not exist. Create it? [y/n]')
        if not _ask_yes_no('create '):
          print(f'Permission to create output directory "{args.output_dir}" '
                'not granted, aborting conversion...')
          sys.exit(1)

    ## Try to make output directory (dir either exists or we have permission to make it)
    makedirs(args.output_dir, exist_ok=True)

    ## Save converted mask
    with open(output_path, 'w', encoding='utf-8') as mask_file:
      mask_file.write(json.dumps(mask_obj, cls=JSONEncoderSDI, indent=2) + '\n')
      if not args.quiet:
        print(f'{src_path}: Output written to {output_path}.')

## Helper functions for main()
def _ask_yes_no(y_action_text=""):
  user_resp = input()
  while user_resp not in ['y', 'n']:
    print(f'Unrecognized response. Please enter "y" {y_action_text}or "n" (cancel).')
    user_resp = input()
  return user_resp == 'y'

## Initialization for main()
if __name__ == '__main__':
  import json
  from argparse import ArgumentParser
  from os import scandir, makedirs
  from pathlib import Path
  import re
  import tomli
  main()
