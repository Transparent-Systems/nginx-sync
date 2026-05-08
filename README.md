# Nginx Sync

![AIP logo](https://aip.transparent.co.nz/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png)

## 🚀 Quick Start

1. **Running nginx-sync**:

    *Running from Source*
    
    a. **Install Python**: Download from [python.org](https://www.python.org/downloads/).

    b. **Download nginx-sync from Github**
      For example type command:
      git clone https://github.com/Transparent-Systems/nginx-sync.git 
    
    c. **Create file .env and add two lines**
    ```bash
      Example content of .env:
      NPM_IDENTITY=your_identity
      NPM_SECRET=your_secret
    ```
  
    d. **Setup Python Virtual Environment on Linux**
    ```bash
      cd nginx-sync
      python -m venv .venv
      source .venv/bin/activate
      pip install -r requirements.txt
      Create file .env and add two lines. For example:

      Run main.py:
      python3 main.py
    ```
    e. **Setup Python Virtual Environment on Windows**
    ```bash
      cd nginx-sync
      python -m venv .venv
      ./.venv/Scripts/activate
      pip install -r requirements.txt
      Run main.py:
      python main.py
    ```

## Script Arguments
You can call `nginx-sync` with several arguments.
Command line arguments will override properties in config.yaml.
To see all arguments type:
python3 main.py -h
OR on Windows:
python main.py -h


* Nginx credentials stored in .env file
* Source and target Nginx server details stored in config.yaml file
* Log configuration stored in log.yaml file
* Nginx Sync can handle one ore more target servers
 


## Features

* Nginx credentials stored in .env file
* Source and target Nginx server details stored in config.yaml file
* Log configuration stored in log.yaml file
* Nginx Sync can handle one ore more target servers
 

## License

This is free software under the terms of the MIT license included in this package.  
See file: LICENSE


## Why Nginx Sync?
The use case for Nginx Sync is:
- You run servers behind a cloudflare tunnel using a cloudflared daemon
- The Cloudflare tunnel connects to a Nginx server that forwards request to web servers, cloud server etc.
- You have 2 or more servers configured with a combo of {cloudflared and Nginx server}
  This provides failover in case one of the servers goes down.
- Now, when make changes to the main Nginx server, you want to propagate thoe changes to the other Nginx servers on your network

Nginx Sync retrieves the proxy hosts of the source Nginx server, checks if there have been any changes ane propagates those changes to all target Nginx servers.


## Acknowledgments

This project was developed with the Google Gemini Code Assist extension in VS Code.

### 👤 Author

John Zoetebier

* Website: [aip.transparent.co.nz](http://aip.transparent.co.nz)
