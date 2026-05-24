# Finance_Dashboard
This a Data engineering and analytics project I'm building to track and analysize my personal finance. 
It is going to track: 
- monthy cashflow
- monthly income
- monthly transactions
- Project future networth and savings

# Components MVP1:
## local folder: 
this contains daily transactions and status of invesents per month. This is the bronze layer
Also data that adheres to the schema will be stored seperately. This is the silver layer
## Python script and duckdb to read daily trascation report and investements and perform aggregations and write to presentation layer
## Streamlit UI: 
### A dasboard to display the below
  -- categorized cashflow per month
  -- projected savings
  -- monthly categorized networth
  -- projected networth:
  ---- money growth
  ---- time to target retirement
  ---- time to house getting paid off
### User interactions on the UI
- Upload financial transactions. The app should highlight rows that don't meet data validity
- User should be able to edit retirment target age and amount and should be able to get back how much they should be contributing
- User should be able to set liquid cash goal


=
