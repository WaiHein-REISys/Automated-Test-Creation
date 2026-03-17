Feature: Free Clinic Applications - Update Application Deadline

As a PSA user, I want to update the application deadline for selected free clinic applications and confirm the changes, ensuring that the new deadline is reflected and actions are confirmed.

### Background:
Given I am on the 'Free Clinic Applications - Update Application Deadline' page
And I have selected at least one application
And I have entered a valid new deadline date

@Functional @Regression @US:12345 @AIGenerated
Scenario: Confirm Update Application Deadline
  When I click on the 'Update Deadline' button
  Then I should be taken to the 'Free Clinic Applications – Update Application Deadline Confirm' page
  And I should see the following note below the page title:
    | Note |
    | The following application(s) will be updated to the deadline listed below. |
  And I should see the following confirmation message below the note:
    | Confirmation |
    | This is a confirmation page! You MUST click on the appropriate button to complete your action. |
  And I should see a read-only grid titled 'Updated Application Deadline' with the selected applications
  And I should see a 'Cancel' button at the bottom left of the page
  And I should see a 'Confirm' button at the bottom right of the page

@Functional @Regression @US:12345 @AIGenerated
Scenario: Cancel Update Application Deadline
  Given I am on the 'Free Clinic Applications – Update Application Deadline Confirm' page
  When I click on the 'Cancel' button
  Then I should be taken back to the 'Free Clinic Applications – Update Application Deadline' page
  And my changes should not be saved
  And the data that I selected should remain populated

@Functional @Regression @US:12345 @AIGenerated
Scenario: Confirm and Save Update Application Deadline
  Given I am on the 'Free Clinic Applications – Update Application Deadline Confirm' page
  When I click on the 'Confirm' button
  Then I should be taken back to the 'Free Clinic Applications – Update Application Deadline' page
  And my changes should be saved
  And I should see the following success message at the top of the page:
    | Success |
    | Application deadline updated. |

@Functional @Regression @US:12345 @AIGenerated
Scenario: Submit Application Before New Deadline
  Given I am a Free Clinic applicant
  And I have an open application
  When I submit the application on or before the new deadline date
  Then the submission should be successful

@Functional @Regression @US:12345 @AIGenerated
Scenario: Prevent Submission After New Deadline
  Given I am a Free Clinic applicant
  And I have an open application
  When I attempt to submit the application after the new deadline date
  Then the submission should be prevented

@Functional @Regression @US:12345 @AIGenerated
Scenario: Display Updated Deadline on External Task List
  Given the application deadline is updated for an application
  When I view the external Task – List page
  Then the new deadline date should be displayed for the application