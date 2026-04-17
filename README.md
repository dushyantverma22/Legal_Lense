# Legal_Lense

## Pinecone ingestion

Dry run:

```powershell
$env:PYTHONPATH="src"
python -m data_ingestion.ingest_pinecone --input .\data --dry-run
```

Real ingestion:

```powershell
$env:PYTHONPATH="src"
python -m data_ingestion.ingest_pinecone --input .\data --namespace local-dev
```

Logs are written to `.\logs\data_ingestion.log`.
