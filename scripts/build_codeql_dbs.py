import csv
import os
import argparse
import subprocess
from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).parent.parent))
from src.config import CODEQL_DB_PATH, PROJECT_SOURCE_CODE_DIR, IRIS_ROOT_DIR, BUILD_INFO, DEP_CONFIGS, DATA_DIR

ALLVERSIONS = {}
if os.path.exists(DEP_CONFIGS):
    ALLVERSIONS = json.load(open(DEP_CONFIGS))

def setup_environment(row):
    """
    Setup environment variables depending on the project language.
    For Java, set JAVA_HOME, Maven, Gradle paths.
    For Python, optionally setup virtualenv (not strictly needed for CodeQL).
    """
    env = os.environ.copy()
    language = row.get("language", "java").lower()

    if language == "java":
        # Set Maven path
        mvn_version = row.get('mvn_version', 'n/a')
        if mvn_version != 'n/a':
            MAVEN_PATH = ALLVERSIONS.get('mvn', {}).get(mvn_version, None)
            if MAVEN_PATH:
                env['PATH'] = f"{os.path.join(MAVEN_PATH, 'bin')}:{env.get('PATH', '')}"
                print(f"Maven path set to: {MAVEN_PATH}")

        # Set Gradle path
        gradle_version = row.get('gradle_version', 'n/a')
        if gradle_version != 'n/a':
            GRADLE_PATH = ALLVERSIONS.get('gradle', {}).get(gradle_version, None)
            if GRADLE_PATH:
                env['PATH'] = f"{os.path.join(GRADLE_PATH, 'bin')}:{env.get('PATH', '')}"
                print(f"Gradle path set to: {GRADLE_PATH}")

        # Set Java home
        java_version = row.get('jdk_version')
        java_home = ALLVERSIONS.get('jdks', {}).get(java_version, None)
        if not java_home:
            raise Exception(f"Java version {java_version} not found in available installations.")
        env['JAVA_HOME'] = java_home
        env['PATH'] = f"{os.path.join(java_home, 'bin')}:{env.get('PATH', '')}"
        print(f"JAVA_HOME set to: {java_home}")

    return env

def create_codeql_database(project_slug, language, db_base_path, sources_base_path, env=None):
    """
    Create a CodeQL database for a project, either Java or Python.
    """
    database_path = os.path.abspath(os.path.join(db_base_path, project_slug))
    database_path_old = os.path.abspath(os.path.join(db_base_path, project_slug+"_old"))
    source_path = os.path.abspath(os.path.join(sources_base_path, project_slug))
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    command_new = [
        "codeql", "database", "create",
        database_path,
        "--source-root", source_path,
        "--language", language,
        "--overwrite"
    ]
    command_old = [
        "./codeql/codeql", "database", "create",
        database_path_old,
        "--source-root", source_path,
        "--language", language,
        "--overwrite"
    ]
    
    if language == "java":
        compile_cmd = "--build-mode=none"
        command_new.append(
            compile_cmd
        )
        command_old.append(compile_cmd)
        

    print(command_new)
    print(f"\nCreating CodeQL database for project: {project_slug} ({language})")
    print(f"Database path: {database_path}")
    print(f"Source path: {source_path}")
    if env:
        print(f"PATH: {env.get('PATH')}")
        if language == "java":
            print(f"JAVA_HOME: {env.get('JAVA_HOME')}")

    try:
        subprocess.run(command_new, env=env, check=True)
        subprocess.run(command_old, env=env, check=True)
        print(f"✅ Successfully created CodeQL database for {project_slug}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create CodeQL database for {project_slug}: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Create CodeQL databases for Java/Python projects')
    parser.add_argument('--project', help='Specific project slug', default=None)
    parser.add_argument('--language', default="java")
    parser.add_argument('--db-path', help='Base path for storing CodeQL databases', default=CODEQL_DB_PATH)
    parser.add_argument('--sources-path', help='Base path for project sources', default=PROJECT_SOURCE_CODE_DIR)
    args = parser.parse_args()

    projects = load_build_info()
    project = args.project
    language = args.language
    # env = setup_environment(project) if language == "java" else None
    create_codeql_database(project, language, args.db_path, args.sources_path)
    # if args.project:
    #     project = next((p for p in projects if p['project_slug'] == args.project), None)
    #     if project:
    #         language = args.language
    #         env = setup_environment(project) if language == "java" else None
    #         create_codeql_database(project['project_slug'], language, args.db_path, args.sources_path, env)
    #     else:
    #         project = args.project
    #         language = args.language
    #         env = setup_environment(project) if language == "java" else None
    #         create_codeql_database(project, language, args.db_path, args.sources_path, env)        
    # else:
    #     for project in projects:
    #         language = args.language
    #         env = setup_environment(project) if language == "java" else None
    #         create_codeql_database(project['project_slug'], language, args.db_path, args.sources_path, env)

LOCAL_BUILD_INFO = os.path.join(DATA_DIR, "build-info", "build_info_local.csv")

def load_build_info():
    """
    Merge local and global build info. Prioritize local.
    """
    build_info = {}

    if os.path.exists(LOCAL_BUILD_INFO):
        with open(LOCAL_BUILD_INFO, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("status", "success") == "success":
                    build_info[row["project_slug"]] = row

    with open(BUILD_INFO, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status", "success") != "success":
                continue
            if row["project_slug"] not in build_info:
                build_info[row["project_slug"]] = row

    return list(build_info.values())

if __name__ == "__main__":
    main()
