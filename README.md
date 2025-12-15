## run_simple
python3 src/iris_input.py CVE-XXXX-XXXX c BR-6208AC_V2_1.02(your product model)     
python scripts/build_codeql_dbs.py --project match_{lang}_0_CVE-xxxx-xxxx_1.0.0 --language {lang}
python3 scripts/get_packages_codeql.py final_{lang}_0_CVE-xxxx-xxxx_1.0.0
python src/iris.py --query cwe-022wLLM --run-id test --llm remote_qwen final_{lang}_0_CVE-xxxx-xxxx_1.0.0  --language {lang} --general 



## Step 1
  python3 src/iris_input.py CVE-XXXX-XXXX c BR-6208AC_V2_1.02(your product model)   

## Step 2 
codeql database create /data_hdd/tzh24/zgc4/projects/tools/iris/src/../data/codeql-dbs/paper_c_5_CVE-XXXX-XXXX_BR-6208AC_V2_1.02(your source code path)    --source-root /data_hdd/tzh24/zgc4/projects/tools/iris/data/project-sources/paper_c_5_CVE-XXXX-XXXX_BR-6208AC_V2_1.02 (your source code DB) \
   --language c\
  --build-mode=none  --overwrite

## Step 3
  python src/iris.py --query cwe-078wLLM --run-id test --llm remote_qwen paper_c_5_CVE-XXXX-XXXX_BR-6208AC_V2_1.02    --language cpp --general --skip-source-post-cache

## 🚀 Set Up
### Using Docker (Recommended)
```bash
docker build -f Dockerfile --platform linux/x86_64 -t iris:latest .
docker run --platform=linux/amd64 -it iris:latest
```
If you intend to configure build tools (Java, Maven, or Gradle) or CodeQL, follow the native setup instructions below.
### Native (Mac/ Linux)
#### Step 1: Setup Conda environment

```sh
conda env create -f environment.yml
conda activate iris
```

If you have a CUDA-capable GPU and want to enable hardware acceleration, install the appropriate CUDA toolkit, for example:
```bash
$ conda install pytorch-cuda=12.1 -c nvidia -c pytorch
```
Replace 12.1 with the CUDA version compatible with your GPU and drivers, if needed.

#### Step 2: Configure Java build tools

To apply IRIS to Java projects, you need to specify the paths to your Java build tools (JDK, Maven, Gradle) in the `dep_configs.json` file in the project root.

The versions of these tools required by each project are specified in `data/build_info.csv`. For instance, `perwendel__spark_CVE-2018-9159_2.7.1` requires JDK 8 and Maven 3.5.0. You can install and manage these tools easily using [SDKMAN!](https://sdkman.io/).

```sh
# Install SDKMAN!
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"

# Install Java 8 and Maven 3.5.0
sdk install java 8.0.452-amzn
sdk install maven 3.5.0
```

#### Step 3: Configure CodeQL

IRIS relies on the CodeQL Action bundle, which includes CLI utilities and pre-defined queries for various CWEs and languages ("QL packs").

If you already have CodeQL installed, specify its location via the `CODEQL_DIR` environment variable in `src/config.py`. Otherwise, download an appropriate version of the CodeQL Action bundle from the [CodeQL Action releases page](https://github.com/github/codeql-action/releases).

- **For the latest version:**
  Visit the [latest release](https://github.com/github/codeql-action/releases/latest) and download the appropriate bundle for your OS:
  - `codeql-bundle-osx64.tar.gz` for macOS
  - `codeql-bundle-linux64.tar.gz` for Linux

- **For a specific version (e.g., 2.15.0):**
  Go to the [CodeQL Action releases page](https://github.com/github/codeql-action/releases), find the release tagged `codeql-bundle-v2.15.0`, and download the appropriate bundle for your platform.

After downloading, extract the archive in the project root directory:

```sh
tar -xzf codeql-bundle-<platform>.tar.gz
```

This should create a sub-directory `codeql/` with the executable `codeql` inside.

Lastly, add the path of this executable to your `PATH` environment variable:

```sh
export PATH="$PWD/codeql:$PATH"
```

### Visualizer

IRIS comes with a visualizer to view the SARIF output files. More detailed instructions can be found in the [docs](https://iris-sast.github.io/iris/features/visualizer.html).

![iris visualizer](docs/assets/visualizer.png)

#### Usage:

1. **Configure paths**: Edit `config.json` to point to your outputs and source directories
2. **Start the server**: Run `python3 server.py`
3. **Open in browser**: Navigate to `http://localhost:8000`
4. **Select a project**: Choose a project from the dropdown to load its analysis results
5. **Filter and explore**: Use the CWE and model filters to explore specific vulnerabilities

## ⚡ Quickstart

Make sure you have followed all of the environment setup instructions before proceeding!

To quickly try IRIS on the example project `perwendel__spark_CVE-2018-9159_2.7.1`, run the following commands:

```sh
# Build the project
python scripts/fetch_and_build.py --filter perwendel__spark_CVE-2018-9159_2.7.1

# Generate the CodeQL database
python scripts/build_codeql_dbs.py --project perwendel__spark_CVE-2018-9159_2.7.1

# Run IRIS analysis
python src/iris.py --query cwe-022wLLM --run-id test --llm qwen2.5-coder-7b perwendel__spark_CVE-2018-9159_2.7.1
```

This will build the project, generate the CodeQL database, and analyze it for CWE-022 vulnerabilities using the specified LLM (qwen2.5-coder-7b). The output of these three steps will be stored under `data/build-info/`, `data/codeql-dbs/`, and `output/` respectively.
Additionally, you can download an image from CWE-Bench-Java from our [Docker Hub](https://hub.docker.com/r/irissast/cwe-bench-java-containers), and use the ```--use-container" flag to run IRIS from a Docker container. You can use this flag with other Docker images as well.
