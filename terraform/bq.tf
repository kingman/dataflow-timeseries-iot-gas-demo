resource "google_storage_bucket" "foglamp_demo_main" {
    name     = "foglamp_demo_main_${var.PROJECT}"
    location = "${var.REGION}"
    uniform_bucket_level_access = true
    force_destroy = true

    provisioner "local-exec" {
        command = <<-EOF
            #!/bin/bash
            export BQ_IMPORT_BUCKET=${google_storage_bucket.foglamp_demo_main.url}
            export PROJECT='${var.PROJECT}'
            export DATASET='${var.DATASET}'
            chmod +x ./scripts/setup_bq.sh
            ./scripts/setup_bq.sh
        EOF
    }
}

resource "google_bigquery_table" "measurements_raw_events" {
    dataset_id = "${var.DATASET}"
    table_id = "measurements_raw_events"
    deletion_protection = false

    schema = <<EOF
    [
        {
            "name":"device_id",
            "type":"STRING",
            "mode":"REQUIRED"
        },
        {
            "name":"event_id",
            "type":"STRING",
            "mode":"REQUIRED"
        }
        ,
        {
            "name":"event_type",
            "type":"STRING",
            "mode":"NULLABLE"
        },
        {
            "name":"severity",
            "type":"STRING",
            "mode":"NULLABLE"
        },
        {
            "name":"device_version",
            "type":"STRING",
            "mode":"NULLABLE"
        },
        {
            "name":"comments",
            "type":"STRING",
            "mode":"NULLABLE"
        },
        {
            "name":"timestamp",
            "type":"TIMESTAMP",
            "mode":"NULLABLE"
        },
        {
            "name":"property_measured",
            "type":"STRING",
            "mode":"NULLABLE"
        },
        {
            "name":"value",
            "type":"FLOAT64",
            "mode":"NULLABLE"
        }
    ]
    EOF
}

resource "google_bigquery_table" "events_summary_view" {
    dataset_id = "${var.DATASET}"
    table_id = "events_summary_view"
    deletion_protection = false

    view {
        use_legacy_sql = false
        query = <<EOF
            WITH T1 AS (
                SELECT 
                    device_id,
                    event_id,
                    event_type,
                    property_measured,
                    comments,
                    severity,
                    MIN(timestamp) AS start_time,
                    MAX(timestamp) AS end_time
                FROM `${var.PROJECT}.${var.DATASET}.measurements_raw_events`
                GROUP BY
                    device_id,
                    event_id,
                    event_type,
                    property_measured,
                    comments,
                    severity
                )

            SELECT device_id, event_id, event_type, start_time, 
                CASE
                    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), end_time, SECOND) > 60 THEN end_time
                    ELSE NULL
                END AS end_time,
                property_measured,
                comments, 
                severity
            FROM T1 
        EOF
    }

    depends_on = [google_bigquery_table.measurements_raw_events]
}

resource "google_bigquery_table" "measurements_raw_events_duration" {
    dataset_id = "${var.DATASET}"
    table_id = "measurements_raw_events_duration"
    deletion_protection = false

    view {
        use_legacy_sql = false
        query = <<EOF
            WITH T1 AS (
                SELECT
                    *,
                    TIMESTAMP_DIFF(
                        timestamp,
                        FIRST_VALUE(timestamp) OVER (PARTITION BY event_id ORDER BY timestamp ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
                        SECOND
                    ) AS duration_seconds
                FROM `${var.PROJECT}.${var.DATASET}.measurements_raw_events`
            )
            SELECT * FROM T1
        EOF
    }

    depends_on = [google_bigquery_table.measurements_raw_events]
}