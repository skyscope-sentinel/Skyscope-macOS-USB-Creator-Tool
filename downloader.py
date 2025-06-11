# This is downloader.py
import time
import sys

def stream_to_file(response, destination_path, total_size=None):
    """
    Streams content from a response object to a file, displaying a progress bar.
    """
    spinner_chars = ['|', '/', '-', '\\']
    chunk_size = 8192  # 8KB
    downloaded_size = 0

    if total_size is None and 'content-length' in response.headers:
        total_size = int(response.headers['content-length'])

    try:
        with open(destination_path, 'wb') as f:
            for i, chunk in enumerate(response.iter_content(chunk_size=chunk_size)):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    if total_size:
                        percentage = (downloaded_size / total_size) * 100
                        progress_bar_length = 50
                        filled_length = int(progress_bar_length * downloaded_size // total_size)
                        bar = '#' * filled_length + ' ' * (progress_bar_length - filled_length)
                        sys.stdout.write(f"\rDownloading... {spinner_chars[i % len(spinner_chars)]} [{bar}] {percentage:.2f}%")
                    else:
                        # If total size is unknown, just show downloaded amount and spinner
                        sys.stdout.write(f"\rDownloading... {spinner_chars[i % len(spinner_chars)]} {downloaded_size / (1024*1024):.2f} MB")

                    sys.stdout.flush()
                    # time.sleep(0.01) # Optional: to make spinner more visible on fast downloads

        sys.stdout.write('\nDownload complete.\n')
        sys.stdout.flush()

    except Exception as e:
        print(f"\nError during download: {e}")
        # Clean up partially downloaded file if necessary
        # import os
        # if os.path.exists(destination_path):
        #     os.remove(destination_path)

# Example Usage (requires a mock response object or a real download)
if __name__ == "__main__":
    # This is a mock response object for demonstration
    class MockChunk:
        def __init__(self, data):
            self.data = data

        def __len__(self):
            return len(self.data)

    class MockResponse:
        def __init__(self, total_bytes, num_chunks):
            self.total_bytes = total_bytes
            self.num_chunks = num_chunks
            self.bytes_per_chunk = total_bytes // num_chunks if num_chunks > 0 else 0
            self.headers = {'content-length': str(total_bytes)}
            self.current_chunk = 0

        def iter_content(self, chunk_size):
            # Ensure chunk_size is positive
            if chunk_size <= 0:
                chunk_size = 8192

            if self.num_chunks == 0 and self.total_bytes > 0 : # Edge case for small files
                 yield b'a' * self.total_bytes
                 return

            for _ in range(self.num_chunks):
                yield b'a' * self.bytes_per_chunk
                self.current_chunk += 1
                time.sleep(0.05) # Simulate network delay

            remaining_bytes = self.total_bytes % self.bytes_per_chunk if self.bytes_per_chunk > 0 else 0
            if remaining_bytes > 0:
                yield b'a' * remaining_bytes


    print("Simulating download (10MB):")
    # Ensure num_chunks is positive for the simulation
    mock_response_total_bytes = 10*1024*1024
    mock_response_num_chunks = 128 if mock_response_total_bytes > 0 else 0
    mock_response = MockResponse(total_bytes=mock_response_total_bytes, num_chunks=mock_response_num_chunks)
    stream_to_file(mock_response, "dummy_download.tmp", total_size=mock_response.total_bytes)

    print("\nSimulating download (unknown size, e.g. 5MB):")
    mock_response_unknown_total_bytes = 5*1024*1024
    mock_response_unknown_num_chunks = 64 if mock_response_unknown_total_bytes > 0 else 0
    mock_response_unknown = MockResponse(total_bytes=mock_response_unknown_total_bytes, num_chunks=mock_response_unknown_num_chunks)
    mock_response_unknown.headers = {} # No content-length
    stream_to_file(mock_response_unknown, "dummy_download_unknown.tmp")

    # Clean up dummy files (optional)
    import os
    if os.path.exists("dummy_download.tmp"):
        os.remove("dummy_download.tmp")
    if os.path.exists("dummy_download_unknown.tmp"):
        os.remove("dummy_download_unknown.tmp")
