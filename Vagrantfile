Vagrant.configure("2") do |config|
  config.vm.communicator = "winrm"

  boxes = {
    "server2008r2" => {
      box: "jborean93/WindowsServer2008R2",
      ip: "172.28.128.11",
    },
    "server2012r2" => {
      box: "jborean93/WindowsServer2012R2",
      ip: "172.28.128.12",
    },
    "server2016" => {
      box: "jborean93/WindowsServer2016",
      ip: "172.28.128.13",
    },
    "server2019" => {
      box: "jborean93/WindowsServer2019",
      ip: "172.28.128.14",
    },
    "server2022" => {
      box: "jborean93/WindowsServer2022",
      ip: "172.28.128.15",
    },
  }

  boxes.each do |name, info|
    config.vm.define name do |node|
      node.vm.box = info[:box]
      node.vm.hostname = name
      node.vm.network "private_network", ip: info[:ip]
      node.vm.provider "libvirt" do |lv|
        lv.memory = 2048
        lv.cpus = 2
      end
    end
  end
end
