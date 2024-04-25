# CHANGELOG

## Release Candidate

### Features

#### 12. 06. 2023 

- Feature: MS-Teams

#### 12. 06. 2023 

- Feature: Load Variables from Config


### Refactoring

- 
#### 26. 05. 2023

- Refactoring :Slack use case

#### 12. 10. 2023

- Refactor : Orchs

#### 20. 11. 2023 

- Refactor the Slack, Email, MS Teams and Attachments 


### Enhancements

- 

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


### Bugfix

- 

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