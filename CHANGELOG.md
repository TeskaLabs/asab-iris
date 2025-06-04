# CHANGELOG


## v25.xx

- Add MS365 Graph API Email support using. (#95 v25.19-alpha)
- Add Wrapper support for MS365 Graph API service.(#96 v25.19-alpha2)
- Fix token expiration issue in MS365 email service.(#98 v25.20-alpha)
- Make smtp service as a fallback (#98 v25.23-alpha)
---

##  v25.17
- Add `PUT /send_ms365_email` endpoint (#91, v25.17-alpha)

---

## v25.10

### Features
- Add `GET /features` endpoint (#90, v25.10-alpha2)
- Add new jinja2 filter quote_plus (#89, v25.10-alpha)

### Fixes
- Remove exits from Kafka handler (#86, v25.08-alpha)

---


## v25.07

### Features
- Tenant configuration (#84)
- Enhancement: Optional services (#83)

### Fixes
- Use correct incoming webhook url (#88)
- Use zookeeper container (#87)
- Email supports TXT templates (#82)

### Refactoring
- Kafka handler refactoring (#81)

---


## v24.42

### Features

#### 12. 06. 2023 

- Feature: MS-Teams

#### 12. 06. 2023 

- Feature: Load Variables from Config

#### 28. 06. 2024 

- Feature: Send SMS

#### 28. 06. 2024 

- Feature: Send SMS


### Refactoring

#### 26. 05. 2023

- Refactoring :Slack use case

#### 12. 10. 2023

- Refactor : Orchs

#### 20. 11. 2023 

- Refactor the Slack, Email, MS Teams and Attachments 


### Enhancements

#### 09. 04. 2023 

- Slack supports attachments.

#### 28. 08. 2023

- Introduce failsafe mechanism for jinja-rendering

#### 12. 09. 2023

- Failsafe message modifications

#### 13. 10. 2023 

- Add "body_max_size": 31457280 to config defaults

#### 13. 10. 2023 

- Sentry Integration.

#### 20. 10. 2023 

-  Method create_nested_dict_from_dots_in_keys uses stack instead of recursion

#### 20. 11. 2023 

- Load variables from json file

#### 16. 01. 2024 

- Upgrade file.

#### 26. 01. 2024 

- Generate ASABIris error for Email

#### 08. 02. 2024 

- Bad templates to be stored in library

#### 08. 02. 2024 

- Add ASABIrisError for Teams and slack

#### 12. 02. 2024 

- Kafka handler : Fallback solution

#### 04. 04. 2024 

- Loading external templates for content wrapping in iris

#### 08.04.2024

- Markdown wrapper configuration.

#### 25.04.2024

- Move Wrapper's to /Templates/Wrapper/

#### 25.04.2024

- Update Wrapper to kafkahandler

#### 16.05.2024

- Change Error

#### 21.11.2024

- Email supports TXT templates


### Bugfix

#### 13. 06. 2023

- Redo Exception message : Patherror 

#### 29. 06. 2023

- Slack , MSteams must be optional

#### 29. 06. 2023

- Email : Subject condition change

#### 14. 07. 2023

- Catch slack error exception

#### 08. 08. 2023

- Adding metrics module so metrics endpoints are accessible

#### 12. 10. 2023

 - Sending email always clears the attachments

#### 15. 11. 2023

- More testing and Fix unit tests testing

#### 14. 12. 2023

- Handle better jinja2 exceptions in Handler

### 14.12.2023

- Fix cicd

### 24.04.2024

- Change SMTP status code


### Maintenance

#### 17. 10. 2024

- Drop support for python 3.7 and 3.8