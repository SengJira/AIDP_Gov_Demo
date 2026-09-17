# DDPE Spark Connect - notebook access and the governance boundary

## Does BIAC enforce for the Spark engine?

**No.** Verified empirically against the `jirawut-demo` DDPE Spark Connect
instance (`sc://jirawut-demo-grpc.ddpe.lab9bgp.com`):

| Fact | Evidence |
| --- | --- |
| Engine identity is `spark`, not a Keycloak user | `SELECT current_user()` returns `spark` |
| Instance launches with only `spark_catalog` + `default` | `SHOW CATALOGS`, `SHOW NAMESPACES` |
| Iceberg runtime is on the server classpath | catalog registration + S3 attempt reach the filesystem layer |
| Direct S3 read fails as launched | `NoAwsCredentialsException` on `s3a://js-demo/warehouse` |
| `SET spark.hadoop.fs.s3a.*` at runtime does NOT reach the Hadoop config | creds set per-session still fail; the FS is fixed at instance launch |
| Baked-in creds target the AIDP s3Proxy | `fs.s3a.endpoint = https://ddae.lab9bgp.com/api/v1/s3Proxy/s3` (access key/secret/token redacted) |

Consequences:

- A DDPE instance launched **with** valid `fs.s3a.*` credentials for the
  governed bucket reads raw Parquet with **no BIAC role checks, no masks,
  no row filters, no BIAC audit events**. Storage credentials are the real
  perimeter.
- To keep governance on a Spark path: route data access through Trino
  (JDBC or the AIDP `s3Proxy` layer) so the request is evaluated by BIAC
  under a real identity - or accept per-bucket/coarse storage controls.
- Dell's intended interactive pattern (DDLH admin guide): Jupyter ->
  DDPE for compute **and** Jupyter -> DDAE for governed data access.

## Connecting from this dev host

The DDPE gRPC ingress presents a cert signed by an internal TitanCA
instance whose root is not in `devin-ca-bundle.pem`, and the istio
gateway routes on the gRPC `:authority` header. Two adaptations are
therefore required from outside the cluster:

1. `scripts/start_spark_proxy.sh` - generates a local CA + cert (SAN
   covers `localhost` and the DDPE host) and starts an haproxy
   TLS-terminating forwarder at `127.0.0.1:15003` with ALPN `h2`.
2. Client-side channel option `grpc.default_authority=<ddpe host>` so
   envoy routes correctly (`sc://localhost` alone yields `UNIMPLEMENTED`
   on every method - including reflection and health checks).

```python
import os
os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = "/tmp/sparktls/ca.pem"
from pyspark.sql.connect.client.core import ChannelBuilder
from pyspark.sql.connect.session import SparkSession as RemoteSession

cb = ChannelBuilder(
    "sc://127.0.0.1:15003/;token=" + os.environ["DDPE_SPARK_TOKEN"],
    channelOptions=[("grpc.default_authority", "jirawut-demo-grpc.ddpe.lab9bgp.com")])
spark = RemoteSession(connection=cb)
spark.sql("SELECT 1").collect()
```

Inside the managed DDPE JupyterLab image (e.g. instance `tk-nb03`, UI at
`https://tk-nb03-ui.ddpe.lab9bgp.com`) the cluster CA is trusted, so a
plain `SparkSession.builder.remote("sc://...:443/;token=...")` should
work without the proxy.

## Token

The `;token=` value is the DDPE access token (also accepted by the DDPE
HTTP API). It is short-lived - get a fresh one with
`dell-data-processing-engine instance status name=<instance>` or the DDPE
UI. Keep it in `.env` as `DDPE_SPARK_TOKEN`; never commit it.

## Notebook

`notebooks/ddpe_spark_governance.ipynb` - runnable end-to-end: connects,
shows `current_user()=spark`, probes the governed table (fails as
launched), then runs the same query through Trino as `gov-tha` where
BIAC applies the TH filter + masks.

## Relaunching an instance with storage access (if ever needed)

Per Dell docs, submit with hadoop confs baked in:

```bash
dell-data-processing-engine submit --name "<name>" --spark-connect \
  --conf spark.hadoop.fs.s3a.endpoint="..." \
  --conf spark.hadoop.fs.s3a.access.key="..." \
  --conf spark.hadoop.fs.s3a.secret.key="..." \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog \
  --conf spark.sql.catalog.spark_catalog.type=hive \
  --conf spark.hadoop.hive.metastore.uris="thrift://<hms>:9083" \
  --pool default
```

If that instance is pointed at `js-demo`, it bypasses BIAC - do not
present it as a governed path.
