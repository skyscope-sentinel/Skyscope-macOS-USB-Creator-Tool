# This is downloader.py
import time
import sys
import requests # Added for making HTTP requests

# Define retryable HTTP status codes
RETRYABLE_STATUS_CODES = [500, 502, 503, 504]

def stream_to_file(url, destination_path, max_retries=5, initial_backoff=1, total_size_override=None):
    """
    Downloads content from a URL to a file, with progress bar and retry mechanism.
    Args:
        url (str): The URL to download from.
        destination_path (str): The path to save the downloaded file.
        max_retries (int): Maximum number of retry attempts.
        initial_backoff (int): Initial delay in seconds for exponential backoff.
        total_size_override (int, optional): Manually provide total size if not in headers
                                             or if headers are unreliable.
    Returns:
        bool: True if download was successful, False otherwise.
    """
    spinner_chars = ['|', '/', '-', '\\']
    chunk_size = 8192  # 8KB

    current_retry = 0
    backoff_time = initial_backoff

    while current_retry <= max_retries:
        response = None  # Ensure response is reset for each retry
        try:
            print(f"\nAttempting to download from {url} (Attempt {current_retry + 1}/{max_retries + 1})...")
            response = requests.get(url, stream=True, timeout=30) # Added timeout
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)

            # If we reach here, status is 2xx
            total_size = total_size_override
            if total_size is None and 'content-length' in response.headers:
                total_size = int(response.headers['content-length'])

            downloaded_size = 0
            with open(destination_path, 'wb') as f:
                for i, chunk in enumerate(response.iter_content(chunk_size=chunk_size)):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if total_size and total_size > 0: # Ensure total_size is not zero
                            percentage = min((downloaded_size / total_size) * 100, 100)
                            progress_bar_length = 50
                            filled_length = int(progress_bar_length * downloaded_size // total_size)
                            filled_length = min(filled_length, progress_bar_length) # Cap filled_length
                            bar = '#' * filled_length + ' ' * (progress_bar_length - filled_length)
                            sys.stdout.write(f"\rDownloading... {spinner_chars[i % len(spinner_chars)]} [{bar}] {percentage:.2f}%")
                        else:
                            sys.stdout.write(f"\rDownloading... {spinner_chars[i % len(spinner_chars)]} {downloaded_size / (1024*1024):.2f} MB")
                        sys.stdout.flush()

            sys.stdout.write('\nDownload complete.\n')
            sys.stdout.flush()
            return True # Download successful

        except requests.exceptions.HTTPError as e:
            # Check if the status code is one we want to retry
            if response is not None and response.status_code in RETRYABLE_STATUS_CODES:
                print(f"\nHTTP Error {response.status_code}: {e}. Retrying...")
            else:
                # Non-retryable HTTP error or no response object to check status
                print(f"\nHTTP Error: {e}. Not retrying.")
                # Potentially clean up partially downloaded file
                # import os
                # if os.path.exists(destination_path): os.remove(destination_path)
                return False # Download failed, non-retryable HTTP error
        except requests.exceptions.RequestException as e:
            # Includes Timeout, ConnectionError, etc. These are generally retryable.
            print(f"\nNetwork Error: {e}. Retrying...")
        except Exception as e:
            # Catch any other unexpected errors during download/write
            print(f"\nAn unexpected error occurred: {e}. Not retrying.")
            # Potentially clean up
            return False


        # If we are here, it means an error occurred and we might retry
        current_retry += 1
        if current_retry <= max_retries:
            print(f"Waiting {backoff_time} seconds before next retry...")
            time.sleep(backoff_time)
            backoff_time *= 2 # Exponential backoff
        else:
            print("\nMaximum retries reached. Download failed.")
            # Potentially clean up
            return False

        finally:
            if response:
                response.close() # Ensure the response is closed on each attempt

    return False # Should be unreachable if loop logic is correct, but as a fallback.


# Example Usage (requires a mock response object or a real download)
if __name__ == "__main__":
    # To test this properly, you'd ideally mock `requests.get` or use a test server.
    # For a simple demonstration, we'll try to download a small public file.
    # Note: This live download might be flaky in some environments.

    # Test URL (small file, usually reliable)
    # Python logo, svg, ~16KB
    test_url_small = "https://www.python.org/static/community_logos/python-logo-master-v3-TM.svg"
    # A larger file (e.g. an image from Wikimedia commons, ~1MB)
    # test_url_larger = "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg"

    temp_file_small = "python_logo.svg"
    # temp_file_larger = "fronlalpstock_big.jpg"

    print(f"Attempting to download: {test_url_small}")
    success_small = stream_to_file(test_url_small, temp_file_small, max_retries=3, initial_backoff=1)
    if success_small:
        print(f"Successfully downloaded {temp_file_small}")
    else:
        print(f"Failed to download {temp_file_small}")

    # print(f"\nAttempting to download: {test_url_larger}")
    # success_larger = stream_to_file(test_url_larger, temp_file_larger, max_retries=3, initial_backoff=1)
    # if success_larger:
    #     print(f"Successfully downloaded {temp_file_larger}")
    # else:
    #     print(f"Failed to download {temp_file_larger}")

    # Example of a URL that will likely fail (404 Not Found)
    test_url_fail = "http://example.com/nonexistentfile.dmg"
    temp_file_fail = "nonexistentfile.dmg"
    print(f"\nAttempting to download a failing URL: {test_url_fail}")
    success_fail = stream_to_file(test_url_fail, temp_file_fail, max_retries=2, initial_backoff=1)
    if not success_fail:
        print(f"Correctly failed to download {temp_file_fail} (as expected).")

    # Clean up dummy files (optional)
    import os
    if os.path.exists(temp_file_small):
        os.remove(temp_file_small)
    # if os.path.exists(temp_file_larger):
    #    os.remove(temp_file_larger)
    if os.path.exists(temp_file_fail): # Should not exist if download fails cleanly
        os.remove(temp_file_fail)
