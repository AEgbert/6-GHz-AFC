# utils
This folder contains supplemental utilities that may be useful in preparing or executing AFC system tests.

## Included Utilities
 * [**./resp2mask.py**](#resp2mask.py): Response-to-Response Mask conversion utility. Automates generation of response masks from a provided AFC inquiry response.

<a name="resp2mask.py"></a>
# Response-to-Response Mask Conversion Utility
## Overview
This utility can generate test harness response masks for a provided AFC inquiry response or set of responses.

## Command-Line Options
### Optional arguments
 * **--cfg**: Path to the TOML config file that specifies how to convert specific fields in the provided response(s) to the response mask(s) (default: `../cfg/resp2mask.toml`)
 * **--output-dir**: Desired output directory for generated masks. If directory doesn't exist, user will be prompted before directory is created (**-y** suppresses prompt) (default: `./masks`, relative to the working directory when the script is executed)
 * **-y**, **--yes**, **--assume-yes**: If provided, will auto answer "yes" to any prompts (overwrites existing files and creates missing directories)
 * **-q**, **--quiet**: Suppress informational messages (implies -y) (skipped file messages will still be printed)

### Required arguments
 * **src**: One or more space-separated paths to single response files or directories of response files (response set) for conversion. Response sets will be aggregated and merged into a single response mask file (see [example](#response-set)).

## Examples
<a name="single-response"></a>
### Converting a single response
To convert a single response, call the conversion script with a path to the single response file:

    # Run the conversion from the current working directory (utils)
    python ./resp2mask.py ../response_sample.json

In this case, the generated mask will be placed in `./masks/response_sample_mask.json`.

Note: The script can be executed from outside of the `utils` directory:

    # Change directory to the root src/harness directory
    cd ..

    # Run the conversion from a different working directory
    python utils/resp2mask.py response_sample.json

In the second example, the generated mask would be placed in the pre-existing `masks` folder in `src/harness` as `response_sample_mask.json`.

<a name="response-set"></a>
### Aggregating multiple responses into a single mask
To create a response mask containing multiple responses in a single file, place all responses that should be grouped into a directory, and provide the path to that directory when calling the script:

    # Create directory defining set of responses
    mkdir example_set

    # Move files to the response set directory (for this example, duplicate the existing response sample file)
    cp ../response_sample.json example_set/response_sample1.json
    cp ../response_sample.json example_set/response_sample2.json
    
    # For sake of example, alter the requestId of the second response to be different from the first (otherwise, the response mask will not be valid)
    sed -i 's/"requestId": "\(.*\)",/"requestId": "\1_duplicate",/g' example_set/response_sample2.json

    # Run the conversion
    python ./resp2mask.py example_set

The resulting mask will be placed in `./masks/example_set_mask.json` and contain expected values from both responses.

Note: A response set may contain only a single response file. In this case, the result will be the same as for the [previous example](#single-response), but the generated mask filename will be derived from the response set directory name and not the encapsulated response filename.

### Generating multiple masks at once
The `src` argument accepts multiple responses/response sets if provided as a space separated list.

    # Assuming utils is the working directory and the response set from the previous example
    python ./resp2mask.py ../response_sample.json example_set

This will create two mask files: `./masks/response_sample_mask.json` and `./masks/example_set_mask.json`. The contents of these files will be identical to the output from the previous two examples.

This command structure is compatible with the output from bash-style command substitution, which is useful for converting all responses/response sets in a directory:

    # Assume a directory responses_to_convert containing a mixture of response JSONs and response set directories
    python ./resp2mask.py responses_to_convert/*

## Config Options
Options for changing the default behavior of how responses are interpreted and converted to response masks can be set using a config file (sample provided in `../cfg/resp2mask.toml`). Full details of these options and their behavior is provided in the sample config file. A summary of the available options are below.
### Power Limit Options
 * **eirp_margins**: Sets upper and lower offsets around the response's maxEirp values to define the ExpectedPowerRange used by the test harness for evaluating other responses
   * Default config value: `{lower = inf, upper = 2.0}` (WFA 2dB upper margin, no lower restriction)
   * Default code value (used if left unspecified in config): `{lower = inf, upper = 0}` (No upper margin, no lower restriction)
 * **psd_margins**: Sets upper and lower offsets around the response's maxPsd values to define the ExpectedPowerRange used by the test harness for evaluating other responses
   * Default config value: `{lower = inf, upper = 2.0}` (WFA 2dB upper margin, no lower restriction)
   * Default code value (used if left unspecified in config): `{lower = inf, upper = 0}` (No upper margin, no lower restriction)
 * **eirp_limits**: Maximum and minimum values for the ExpectedPowerRanges generated for maxEirp. These limits are intended to enforce regulatory limits on the acceptable range of responses from an AFC.
   * Default value: `{lower = -inf, upper = 36.0}` (FCC maximum value, no lower limit)
   * Default code value (used if left unspecified in config): `{lower = -inf, upper = inf}` (No upper or lower limit)
 * **psd_limits**: Maximum and minimum values for the ExpectedPowerRanges generated for maxPsd. These limits are intended to enforce regulatory limits on the acceptable range of responses from an AFC.
   * Default value: `{lower = -inf, upper = 23.0}` (FCC maximum value, no lower limit)
   * Default code value (used if left unspecified in config): `{lower = -inf, upper = inf}` (No upper or lower limit)

### Response Code Options
 * **expect_less_specific_error**: If the response contains an optional, more-specific ResponseCode (such as INVALID_VALUE), this option allows the response mask to also expect GENERAL_FAILURE without causing an UNEXPECTED test result.
   * Default value: `True`
 * **permit_any_code**: Creates a response mask that does not disallow any ResponseCodes, but will warn if a response provides a ResponseCode that isn't expected by the mask.
   * Default value: `False`

### Other Options
 * **exclude_extensions**: Excludes any VendorExtension objects contained in the response from the generated response object. Otherwise, all VendorExtensions will be transferred as-is (conversion errors may result if VendorExtension is invalid according to the SDI specification).
   * Default value: `True`