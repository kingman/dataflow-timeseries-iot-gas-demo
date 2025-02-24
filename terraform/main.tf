provider "google" {
    project = "${var.PROJECT}"
    region  = "${var.REGION}"
    zone    = "${var.ZONE}"
}

resource "tls_private_key" "google_compute_engine_ssh" {
    algorithm = "RSA"
    rsa_bits  = 4096
}

resource "google_service_account" "foglamp-publisher" {
  account_id   = "foglamp-publisher"
  display_name = "FogLAMP Publisher"
}

resource "google_project_iam_member" "foglamp-publisher" {
  project = var.PROJECT
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.foglamp-publisher.email}"
}

resource "google_service_account_key" "foglamp-publisher" {
  service_account_id = google_service_account.foglamp-publisher.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

resource "local_file" "foglamp-publisher" {
    content  = base64decode(google_service_account_key.foglamp-publisher.private_key)
    filename = "./certs/credentials.json"
}

resource "google_compute_instance" "instance_with_ip" {
    name         = "foglamp-demo-instance"
    machine_type = "e2-standard-2"
    deletion_protection = false

    tags = ["http-server","https-server"]

    boot_disk {
        initialize_params {
            image = "ubuntu-1804-bionic-v20210623"
            size = 100
            type = "pd-standard"
        }
    }

    network_interface {
        network = "default"
        access_config {
        }
    }

    metadata = {
        ssh-keys = "${var.USER}:${tls_private_key.google_compute_engine_ssh.public_key_openssh}"
    }

    metadata_startup_script = file("./scripts/setup_vm.sh")

}

output "internal_ip" {
    value = google_compute_instance.instance_with_ip.network_interface.0.network_ip
}