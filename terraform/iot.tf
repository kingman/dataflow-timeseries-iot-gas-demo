resource "google_pubsub_topic" "foglamp-demo" {
    name = "foglamp-demo"
}

resource "google_pubsub_topic" "foglamp-demo-raw" {
    name = "foglamp-demo-raw"
}

resource "google_pubsub_topic" "foglamp-demo-events" {
    name = "foglamp-demo-events"
}
