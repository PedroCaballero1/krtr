# krtr

## S3 downloads

`krtr` can download a single file or a whole "directory" (key prefix) from S3.

### Credentials

Credentials are read from environment variables, optionally loaded from a `.env` file in the
working directory (do not commit it).

To set them up:

1. Copy the example file to `.env`:

   ```bash
   cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
   ```

2. Open `.env` and replace the placeholder values with your own keys. Only
   `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are required; leave the optional ones empty
   if you don't need them.
3. Run any `krtr database s3 ...` command from the same directory; the file is loaded
   automatically.

The variables are:

```dotenv
AWS_ACCESS_KEY_ID=...          # required
AWS_SECRET_ACCESS_KEY=...      # required
AWS_SESSION_TOKEN=...          # optional, for temporary credentials
AWS_DEFAULT_REGION=...         # optional
AWS_ENDPOINT_URL=...           # optional, for S3-compatible services such as MinIO
BUCKET_NAME=...                # optional, default bucket for paths without `s3://bucket`
```

### CLI

```bash
# List the files under a directory (one per line, relative to it)
krtr database s3 list-files s3://my-bucket/data

# One file
krtr database s3 download-file s3://my-bucket/data/report.csv ./downloads/report.csv

# Every object under a prefix, preserving the sub-structure
krtr database s3 download-directory s3://my-bucket/data ./downloads/data
```

When `BUCKET_NAME` is set you can omit the bucket and pass just the key or prefix
(`krtr database s3 download-file data/report.csv ./report.csv`). A bucket written in the path
(`s3://other-bucket/...`) always overrides the default.

Parent directories are created as needed. Add `--verbose` before the subcommand
(`krtr --verbose database s3 ...`) for debug logging. Failures (bad path, missing credentials,
empty prefix, S3 errors) exit with code 1.

### Python

```python
from pathlib import Path

from krtr.database.s3.client import S3Client

client = S3Client()  # or S3Client(S3Config(...))
client.download_file("s3://my-bucket/data/report.csv", Path("report.csv"))
result = client.download_directory("s3://my-bucket/data", Path("downloads"))
print(result.downloaded_files)
```

Directory downloads paginate through all objects, skip folder marker keys, only match the exact
prefix (`data` never matches `data2/`), and refuse keys that would be written outside the local
directory.
