### 统计每个交易日的前20个交易日的数据
```python
# 每个交易日的前20个交易日的交易量的最大值，平均值, 方差, 平均值+3σ
df['volumn_max'] = df['volumn'].rolling(window=20).max()
df['volumn_mean'] = df['volumn'].rolling(window=20).mean()
df['volumn_var'] = df['volumn'].rolling(window=20).var()

df['volumn_mean_plus_3sigma'] = df['volumn'].rolling(window=20).mean() + 3 * df['volumn'].rolling(window=20).std()


# ！！！！可以用shift(1) 计算前20个交易日的数据(不包括当日)
df['volumn_mean_plus_3sigma'] = df['volumn'].rolling(window=20).max().shift(1)
```