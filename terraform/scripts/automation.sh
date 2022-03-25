
git clone https://github.com/kingman/dataflow-timeseries-iot-gas-demo
cd dataflow-timeseries-iot-gas-demo/terraform

export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value core/project)
envsubst '${GOOGLE_CLOUD_PROJECT}' <  variables.temp > variables.tfvars

gcloud services disable dataflow.googleapis.com
gcloud services enable dataflow.googleapis.com



terraform init 
terraform apply -var-file="variables.tfvars"


--

wget https://raw.githubusercontent.com/kingman/dataflow-timeseries-iot-gas-demo/main/terraform/scripts/setup_vm.sh
chmod +x setup_vm.sh
./setup_vm.sh

sudo sed -i "s/User=%I/User=$USER/g" /lib/systemd/system/chrome-remote-desktop@.service

sudo pip3 upgrade pip