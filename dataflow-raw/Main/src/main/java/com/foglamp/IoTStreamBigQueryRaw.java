/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.foglamp;

import com.foglamp.utils.BigQuerySchemaCreate;
import com.foglamp.utils.Options;
import com.foglamp.utils.messageParsing.JsonToTableRow;
import com.foglamp.utils.customFn.CreateKey;
import com.foglamp.utils.customFn.RemoveKey;
import com.foglamp.utils.messageParsing.TableRowFormat;
import com.foglamp.utils.messageParsing.GsonConvertToString;

import com.google.api.services.pubsub.model.PubsubMessage;
import com.google.api.services.bigquery.model.TableRow;
import com.google.api.services.bigquery.model.TableSchema;
import java.io.IOException;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.CreateDisposition;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.WriteDisposition;
import org.apache.beam.sdk.io.gcp.pubsub.PubsubIO;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.transforms.Flatten;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.windowing.Sessions;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionTuple;
import org.apache.beam.sdk.values.TupleTag;
import org.apache.beam.sdk.values.TupleTagList;
import org.joda.time.Duration;

import org.apache.beam.sdk.io.TextIO;

public class IoTStreamBigQueryRaw {

  public static void main(String[] args) throws IOException {

    Options options = PipelineOptionsFactory.fromArgs(args).as(Options.class);
    options.setStreaming(true);

    String destination_table = options.getOutputTable();
    String input_topic = options.getInputTopic();
    String output_topic = options.getOutputTopic();
    int timer_size = options.getTimerSize();

    Pipeline pipeline = Pipeline.create(options);

    PCollection<TableRow> messages = null;
    messages =
        pipeline
            .apply("Pull PubSub Messages", PubsubIO.readStrings().fromTopic(input_topic))
            .apply("To TableRows", new JsonToTableRow());

    PCollection<Iterable<TableRow>> message_strings = messages.apply("Format TableRows", ParDo.of(new TableRowFormat()));
    PCollection<TableRow> flat_rows = message_strings.apply("Flatten TableRows", Flatten.iterables());

    TableSchema schema = BigQuerySchemaCreate.createSchema();
    flat_rows.apply(
        "Write to BigQuery",
        BigQueryIO.writeTableRows()
            .withSchema(schema)
            .withCreateDisposition(CreateDisposition.CREATE_IF_NEEDED)
            .withWriteDisposition(WriteDisposition.WRITE_APPEND)
            .to(destination_table));

    PCollection<String> output_raw = flat_rows.apply("Rows to String", ParDo.of(new GsonConvertToString()));

    output_raw.apply("Rows to PubSub", PubsubIO.writeStrings().to(output_topic)); 

    pipeline.run();
  }
}