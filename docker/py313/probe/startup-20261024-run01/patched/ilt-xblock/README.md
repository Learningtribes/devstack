# XBlock ILT (Instructor Lead Training)

This xblock is used for cooperate online training sessions with offline training sessions. Teacher can use this xblock to create an offline sessions and ask students to enroll, then he can grade students on this xblock. With this, we can centralize all the usage data online.

## Features

### For students

- Enroll/Unenroll session
- add enrolled session to calendar

### For Teachers

- All features for students
- Training session management (CRUD)
- Evaluate students

## Install, Quick Start

*Attention: this xblock use vuejs as its javascripts framework, be sure to include vuejs in your cms/lms base templates.*

### install ILT xblock:

1. Clone this repo to your machine (if you are using devstack, clone it in your devstack)

   ```shell
   git clone https://github.com/Learningtribes/xblock-ilt.git /your/path
   ```

2. Activate your virtualenv

   ```shell
   source /edx/app/edxapp/venvs/edxapp/bin/activate
   ```

3. Install this package (if you want to edit it, install with `-e` options), **be careful** with the trailing slash, if you don't have it, pip will try to search this package from repo.

   ```shell
   pip install /your/path/
   ```

### Activate ILT in your course

1. Go to Studio, find the course you want to activate ILT
2. Settings -> Advanced Settings -> Advanced Module List
3. Add `"ILT"` to the list, don't forgot the trailing comma
4. Visit any unit in your course, visit "Advanced", you should see ILT in the list. 

## Known Issues

- …