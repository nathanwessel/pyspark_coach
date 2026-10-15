# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Setup
# MAGIC ## Imports
# COMMAND ----------
from pyspark.sql.functions import min, max, sum
orders = spark.table("demo.orders")
customers = spark.table("demo.customers")
filters = {"region": "east"}
# COMMAND ----------
# MAGIC %md
# MAGIC # Transformations
# MAGIC ## Join
# COMMAND ----------
joined = orders.join(customers, orders.customer_id == customers.customer_id, "inner")
# COMMAND ----------
# MAGIC %pip install pyarrow
