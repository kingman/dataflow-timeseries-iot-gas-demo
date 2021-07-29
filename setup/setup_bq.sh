#!/bin/bash

#chmod +x setup_bq.sh

export DATASET="foglamp_demo_test"
export PROJECT="sandbox-keyera-poc"
export bqImportBucket="gs://foglamp/imports"

gsutil cp ./setup/dimension_tables/*.json ${bqImportBucket}

bq --location=us mk \
    --dataset \
    ${PROJECT}:${DATASET}

for filename in ./setup/dimension_tables/*.json; do
    y=${filename%.json}

    bq load \
        --source_format=NEWLINE_DELIMITED_JSON \
        --autodetect \
        ${DATASET}.${y##*/} \
        gs://foglamp/imports/$(basename $filename) \
        ./setup/dimension_tables/${y##*/}

done