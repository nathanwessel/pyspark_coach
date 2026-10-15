# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install pyarrow
# COMMAND ----------
# MAGIC %md
# MAGIC # 📦 Setup
# MAGIC ## 📚 Imports
# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.functions import min as spark_min, max as spark_max, sum as spark_sum
orders_df = spark.table("demo.orders")
customers_df = spark.table("demo.customers")
filters_dict = {"region": "east"}
# COMMAND ----------
# MAGIC %md
# MAGIC # 🔧 Transformations
# MAGIC ## 🔗 Join
# COMMAND ----------
joined_df = orders_df.alias("o").join(
    customers_df.alias("c"),
    F.col("o.customer_id") == F.col("c.customer_id"),
    "inner",
)
