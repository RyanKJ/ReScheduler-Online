from django import forms

class CalendarForm(forms.Form):
    department = forms.CharField(label='Department', max_length=100)