import copy

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from Strategy import *

sns.set()


# %%
class Agent:

    def __init__(self, portfolio, data, trading_strategies, rebalancing_strategies, cycle, max_holding):
        """
        portfolio: dictionary (accounting book)
        Max_holding is the maximum number of stocks this agent can hold
        Cycle is the rebalancing period
        Data is the dataset
        Strategies is which factor investing strategy this Agent has in disposal
        """
        self.portfolio = portfolio
        self.data = data
        self.trading_strategies = trading_strategies
        self.rebalancing_strategies = rebalancing_strategies
        self.cycle = cycle
        self.equity = INITIAL_BALANCE
        self.re = float()
        self.tran_cost = float()
        self.rf = np.power(RISKFREE, self.cycle / 252)
        self.max_holding = max_holding

    def PitchStock(self, trading_strategy, time):
        """
        Argument trading_strategy: a function that takes (df, cycle, time) as argument
        return ranking: list of stocks that should invest
        """
        cycle = self.cycle
        data = self.data
        max_holding = self.max_holding
        ranking = {}
        for i in ticker:
            metric = trading_strategy(data[i], cycle, time)
            if metric is not None and not math.isnan(metric):
                ranking[i] = metric
        result = sorted(ranking, key=ranking.get)[:max_holding]
        return result

    def Rebalancing(self, ranking, rebalancing_strategy, time):
        """
        Argument ranking: result from Agent.PitchStock
                rebalancing_strategy: a function that takes (df, ranking, time, cycle) as argument
                return target_portfolio: dictionary {Stock: # of shares}
        """
        cycle = self.cycle
        data = self.data
        cash = self.portfolio['cash']
        # assume that cash earns risk-free rate interest
        equity = self.get_Equity(time) + cash * (self.rf - 1)
        target_portfolio = {}
        weight = np.array(rebalancing_strategy(data, ranking, time, cycle))
        weight = (weight * equity).astype(int)
        for w, stock in zip(weight, ranking):
            price = data[stock].iloc[time]
            shares = w // price
            target_portfolio[stock] = shares
            equity -= shares * price
        target_portfolio['cash'] = equity
        return target_portfolio

    def get_Equity(self, time):
        """
        return the equity value for a given time
            sum weight * price
        """
        data = self.data
        portfolio = copy.deepcopy(self.portfolio)
        cash = portfolio['cash']
        total_equity = cash
        # compute the stock value
        del portfolio['cash']
        ticker = list(portfolio)
        shares = np.array(list(portfolio.values()))
        price = np.matrix(data[ticker].iloc[time])
        total_equity += price @ shares
        return total_equity.item()

    def Trading(self, target_portfolio, time):
        """
        Argument target_portfolio: a dictionary get from rebalance 
                    (what Agent.portfolio should be after trading)
        returns nothing but update:
                equity, portfolio, re, tran_cost
        """
        # take all necessary attributes from the class
        cost = 0
        portfolio = self.portfolio
        # selling and adjust share
        for i in list(portfolio):
            if i not in target_portfolio and i != 'cash':
                cost += portfolio[i] * TRANS_COST
            elif i in target_portfolio and i != 'cash':
                diff = abs(portfolio[i] - target_portfolio[i])
                cost += diff * TRANS_COST
        # buying
        for i in target_portfolio:
            if i not in portfolio:
                cost += target_portfolio[i] * TRANS_COST
        # update all the attribute of the agent
        self.tran_cost += cost
        self.portfolio = target_portfolio
        self.equity = self.get_Equity(time) - cost
        self.re = self.equity / INITIAL_BALANCE

    def get_Vol(self, time):
        """
        use portfolio weights to calcualte equity paths in this cycle
        and then compute its variance
        """
        cycle = self.cycle
        data = self.data
        portfolio = copy.deepcopy(self.portfolio)
        del portfolio['cash']
        # this is a vector of max_holding number of elements
        shares = np.array(list(portfolio.values()))
        # ticker in the portfolio except cash
        ticker = list(portfolio)
        price_matrix = np.matrix(data[ticker].iloc[time + 1 - cycle:time + 1])
        equity_path = price_matrix @ shares
        return equity_path

    def BackTesting_Single(self, trading_strategy, rebalancing_strategy):
        """
        This is backtsting for one single combination of trading and rebalancing strategy
        Return the total return, volatility and Sharpe ratio
        """
        cycle = self.cycle
        data = self.data
        print("Trading strategy: %s \n" % trading_strategy.__name__)
        print("Rebalancing strategy: %s \n" % rebalancing_strategy.__name__)
        T = len(data) // cycle
        print("We are rebalancing for %s number of times." % T)
        portfolio_path = []
        for i in range(1, T):
            time = i * cycle
            ranking = self.PitchStock(trading_strategy, time)
            target_portfolio = self.Rebalancing(ranking, rebalancing_strategy, time)
            # get volatility before portfolio updates
            portfolio_path.append(self.get_Vol(time))
            self.Trading(target_portfolio, time)
            print("Rebalancing for %s time!" % i)
        vol = np.std(portfolio_path) / np.sqrt(T * cycle) / 100
        # annualized return
        annual_return = (np.power(self.re, 252 // cycle / T) - 1) * 100
        # annualized risk free
        total_rf = np.power(RISKFREE, cycle * T / 252)
        sharpe = (self.re - total_rf) / vol
        return annual_return, vol, sharpe

    def BackTesting(self):
        """
        This is backtsting for all strategies
        Return two dictionary
            1. return for each strategy
            2. overall cost for each strategy
        """
        trading_strategies = self.trading_strategies
        rebalancing_strategies = self.rebalancing_strategies
        print("There are %s trading strategies and %s rebalancing strategies we are testing." % (
            len(trading_strategies), len(rebalancing_strategies)))
        print("They are: ")
        for i in trading_strategies:
            print("     %s \n" % i.__name__)
        for i in rebalancing_strategies:
            print("     %s \n" % i.__name__)
        portfolio_re = pd.DataFrame(index=[x.__name__ for x in rebalancing_strategies],
                                    columns=[x.__name__ for x in trading_strategies])
        portfolio_vol = pd.DataFrame(index=[x.__name__ for x in rebalancing_strategies],
                                     columns=[x.__name__ for x in trading_strategies])
        portfolio_sharpe = pd.DataFrame(index=[x.__name__ for x in rebalancing_strategies],
                                        columns=[x.__name__ for x in trading_strategies])
        for col, trading_strategy in enumerate(trading_strategies):
            for row, rebalancing_strategy in enumerate(rebalancing_strategies):
                # use BackTesting_Single to get the three value of metrics needed
                total_return, vol, sharpe = self.BackTesting_Single(trading_strategy, rebalancing_strategy)
                portfolio_re.iloc[row][col] = total_return
                portfolio_vol.iloc[row][col] = vol
                portfolio_sharpe.iloc[row][col] = sharpe
                # reset balance, equity, re, and transaction cost for the agent
                self.reset()
                print("\n")
        # turn this dictionary into a nicely presentable dataframe
        return portfolio_re, portfolio_vol, portfolio_sharpe

    def reset(self):
        """
        This reset the Agent to its initial holding. 
        Apply this method between testing different strategies.
        """
        self.portfolio = {'cash': INITIAL_BALANCE}
        self.equity = INITIAL_BALANCE
        self.re = float()
        self.tran_cost = float()


def data_preprocess(dta):
    dta['Date'] = pd.to_datetime(dta['Date'], format='%Y-%m-%d')
    dta = dta.set_index(dta['Date'])
    dta.drop(['Date'], axis=1, inplace=True)
    dta.dropna(how='all', inplace=True)
    for tick in dta.columns:
        tick_series = dta[tick]
        start_pos = tick_series.first_valid_index()
        valid_series = tick_series.loc[start_pos:]
        if valid_series.isna().sum() > 0:
            dta.drop(tick, axis=1, inplace=True)

    for tick in dta.columns:
        dta[tick] = dta[tick].mask(dta[tick] == 0).ffill(downcast='infer')

    return dta

if __name__ == '__main__':
    df = pd.read_csv("SP500.csv")
    # df.drop(['Unnamed: 0'], axis=1, inplace=True)
    print(df.shape)
    df = data_preprocess(df)
    print(df.shape)
    ticker = list(df.columns)
    ticker.remove('SPY')

    INITIAL_BALANCE = 50000
    TRANS_COST = 0.00
    # define the risk-free rate
    RISKFREE = 1.00

    wsw = Agent({'cash': INITIAL_BALANCE}, df, trading_strategies, rebalancing_strategies[1:], cycle=10, max_holding=20)

    return_chart, vol_chart, sharpe_chart = wsw.BackTesting()
    '''
    return_chart = return_chart.astype(float)
    plt.title('Return Heatmap')
    sns.heatmap(return_chart, annot=True, square=True, cmap='RdBu')

    vol_chart = vol_chart.astype(float)
    plt.title('Volatility Heatmap')
    sns.heatmap(vol_chart, annot=True, square=True, cmap='RdBu')

    sharpe_chart = sharpe_chart.astype(float)
    plt.title('Sharpe Ratio Heatmap')
    sns.heatmap(sharpe_chart, annot=True, square=True, cmap='RdBu')
    '''