### 资源
[东财数据源](https://pkg.go.dev/github.com/axiaoxin-com/x-stock/datacenter/eastmoney#section-readme)



### 数据说明
<details> <summary> 现金流数据 xjll</summary>

```
type CashflowData struct {
	Secucode                  string         `json:"SECUCODE"`
	SecurityCode              string         `json:"SECURITY_CODE"`
	SecurityNameAbbr          string         `json:"SECURITY_NAME_ABBR"`
	OrgCode                   string         `json:"ORG_CODE"`
	OrgType                   string         `json:"ORG_TYPE"`
	ReportDate                string         `json:"REPORT_DATE"`
	ReportType                FinaReportType `json:"REPORT_TYPE"`
	ReportDateName            string         `json:"REPORT_DATE_NAME"`
	SecurityTypeCode          string         `json:"SECURITY_TYPE_CODE"`
	NoticeDate                string         `json:"NOTICE_DATE"`
	UpdateDate                string         `json:"UPDATE_DATE"`
	Currency                  string         `json:"CURRENCY"`
	SalesServices             float64        `json:"SALES_SERVICES"`
	DepositInterbankAdd       float64        `json:"DEPOSIT_INTERBANK_ADD"`
	LoanPbcAdd                float64        `json:"LOAN_PBC_ADD"`
	OfiBfAdd                  float64        `json:"OFI_BF_ADD"`
	ReceiveOrigicPremium      float64        `json:"RECEIVE_ORIGIC_PREMIUM"`
	ReceiveReinsureNet        float64        `json:"RECEIVE_REINSURE_NET"`
	InsuredInvestAdd          float64        `json:"INSURED_INVEST_ADD"`
	DisposalTfaAdd            float64        `json:"DISPOSAL_TFA_ADD"`
	ReceiveInterestCommission float64        `json:"RECEIVE_INTEREST_COMMISSION"`
	BorrowFundAdd             float64        `json:"BORROW_FUND_ADD"`
	LoanAdvanceReduce         float64        `json:"LOAN_ADVANCE_REDUCE"`
	RepoBusinessAdd           float64        `json:"REPO_BUSINESS_ADD"`
	ReceiveTaxRefund          float64        `json:"RECEIVE_TAX_REFUND"`
	ReceiveOtherOperate       float64        `json:"RECEIVE_OTHER_OPERATE"`
	OperateInflowOther        float64        `json:"OPERATE_INFLOW_OTHER"`
	OperateInflowBalance      float64        `json:"OPERATE_INFLOW_BALANCE"`
	TotalOperateInflow        float64        `json:"TOTAL_OPERATE_INFLOW"`
	BuyServices               float64        `json:"BUY_SERVICES"`
	LoanAdvanceAdd            float64        `json:"LOAN_ADVANCE_ADD"`
	PbcInterbankAdd           float64        `json:"PBC_INTERBANK_ADD"`
	PayOrigicCompensate       float64        `json:"PAY_ORIGIC_COMPENSATE"`
	PayInterestCommission     float64        `json:"PAY_INTEREST_COMMISSION"`
	PayPolicyBonus            float64        `json:"PAY_POLICY_BONUS"`
	PayStaffCash              float64        `json:"PAY_STAFF_CASH"`
	PayAllTax                 float64        `json:"PAY_ALL_TAX"`
	PayOtherOperate           float64        `json:"PAY_OTHER_OPERATE"`
	OperateOutflowOther       float64        `json:"OPERATE_OUTFLOW_OTHER"`
	OperateOutflowBalance     float64        `json:"OPERATE_OUTFLOW_BALANCE"`
	TotalOperateOutflow       float64        `json:"TOTAL_OPERATE_OUTFLOW"`
	OperateNetcashOther       float64        `json:"OPERATE_NETCASH_OTHER"`
	OperateNetcashBalance     float64        `json:"OPERATE_NETCASH_BALANCE"`
	// 经营活动产生的现金流量净额
	NetcashOperate           float64 `json:"NETCASH_OPERATE"`
	WithdrawInvest           float64 `json:"WITHDRAW_INVEST"`
	ReceiveInvestIncome      float64 `json:"RECEIVE_INVEST_INCOME"`
	DisposalLongAsset        float64 `json:"DISPOSAL_LONG_ASSET"`
	DisposalSubsidiaryOther  float64 `json:"DISPOSAL_SUBSIDIARY_OTHER"`
	ReducePledgeTimedeposits float64 `json:"REDUCE_PLEDGE_TIMEDEPOSITS"`
	ReceiveOtherInvest       float64 `json:"RECEIVE_OTHER_INVEST"`
	InvestInflowOther        float64 `json:"INVEST_INFLOW_OTHER"`
	InvestInflowBalance      float64 `json:"INVEST_INFLOW_BALANCE"`
	TotalInvestInflow        float64 `json:"TOTAL_INVEST_INFLOW"`
	ConstructLongAsset       float64 `json:"CONSTRUCT_LONG_ASSET"`
	InvestPayCash            float64 `json:"INVEST_PAY_CASH"`
	PledgeLoanAdd            float64 `json:"PLEDGE_LOAN_ADD"`
	ObtainSubsidiaryOther    float64 `json:"OBTAIN_SUBSIDIARY_OTHER"`
	AddPledgeTimedeposits    float64 `json:"ADD_PLEDGE_TIMEDEPOSITS"`
	PayOtherInvest           float64 `json:"PAY_OTHER_INVEST"`
	InvestOutflowOther       float64 `json:"INVEST_OUTFLOW_OTHER"`
	InvestOutflowBalance     float64 `json:"INVEST_OUTFLOW_BALANCE"`
	TotalInvestOutflow       float64 `json:"TOTAL_INVEST_OUTFLOW"`
	InvestNetcashOther       float64 `json:"INVEST_NETCASH_OTHER"`
	InvestNetcashBalance     float64 `json:"INVEST_NETCASH_BALANCE"`
	// 投资活动产生的现金流量净额
	NetcashInvest          float64 `json:"NETCASH_INVEST"`
	AcceptInvestCash       float64 `json:"ACCEPT_INVEST_CASH"`
	SubsidiaryAcceptInvest float64 `json:"SUBSIDIARY_ACCEPT_INVEST"`
	ReceiveLoanCash        float64 `json:"RECEIVE_LOAN_CASH"`
	IssueBond              float64 `json:"ISSUE_BOND"`
	ReceiveOtherFinance    float64 `json:"RECEIVE_OTHER_FINANCE"`
	FinanceInflowOther     float64 `json:"FINANCE_INFLOW_OTHER"`
	FinanceInflowBalance   float64 `json:"FINANCE_INFLOW_BALANCE"`
	TotalFinanceInflow     float64 `json:"TOTAL_FINANCE_INFLOW"`
	PayDebtCash            float64 `json:"PAY_DEBT_CASH"`
	AssignDividendPorfit   float64 `json:"ASSIGN_DIVIDEND_PORFIT"`
	SubsidiaryPayDividend  float64 `json:"SUBSIDIARY_PAY_DIVIDEND"`
	BuySubsidiaryEquity    float64 `json:"BUY_SUBSIDIARY_EQUITY"`
	PayOtherFinance        float64 `json:"PAY_OTHER_FINANCE"`
	SubsidiaryReduceCash   float64 `json:"SUBSIDIARY_REDUCE_CASH"`
	FinanceOutflowOther    float64 `json:"FINANCE_OUTFLOW_OTHER"`
	FinanceOutflowBalance  float64 `json:"FINANCE_OUTFLOW_BALANCE"`
	TotalFinanceOutflow    float64 `json:"TOTAL_FINANCE_OUTFLOW"`
	FinanceNetcashOther    float64 `json:"FINANCE_NETCASH_OTHER"`
	FinanceNetcashBalance  float64 `json:"FINANCE_NETCASH_BALANCE"`
	// 筹资活动产生的现金流量净额
	NetcashFinance               float64 `json:"NETCASH_FINANCE"`
	RateChangeEffect             float64 `json:"RATE_CHANGE_EFFECT"`
	CceAddOther                  float64 `json:"CCE_ADD_OTHER"`
	CceAddBalance                float64 `json:"CCE_ADD_BALANCE"`
	CceAdd                       float64 `json:"CCE_ADD"`
	BeginCce                     float64 `json:"BEGIN_CCE"`
	EndCceOther                  float64 `json:"END_CCE_OTHER"`
	EndCceBalance                float64 `json:"END_CCE_BALANCE"`
	EndCce                       float64 `json:"END_CCE"`
	Netprofit                    float64 `json:"NETPROFIT"`
	AssetImpairment              float64 `json:"ASSET_IMPAIRMENT"`
	FaIrDepr                     float64 `json:"FA_IR_DEPR"`
	OilgasBiologyDepr            float64 `json:"OILGAS_BIOLOGY_DEPR"`
	IrDepr                       float64 `json:"IR_DEPR"`
	IaAmortize                   float64 `json:"IA_AMORTIZE"`
	LpeAmortize                  float64 `json:"LPE_AMORTIZE"`
	DeferIncomeAmortize          float64 `json:"DEFER_INCOME_AMORTIZE"`
	PrepaidExpenseReduce         float64 `json:"PREPAID_EXPENSE_REDUCE"`
	AccruedExpenseAdd            float64 `json:"ACCRUED_EXPENSE_ADD"`
	DisposalLongassetLoss        float64 `json:"DISPOSAL_LONGASSET_LOSS"`
	FaScrapLoss                  float64 `json:"FA_SCRAP_LOSS"`
	FairvalueChangeLoss          float64 `json:"FAIRVALUE_CHANGE_LOSS"`
	FinanceExpense               float64 `json:"FINANCE_EXPENSE"`
	InvestLoss                   float64 `json:"INVEST_LOSS"`
	DeferTax                     float64 `json:"DEFER_TAX"`
	DtAssetReduce                float64 `json:"DT_ASSET_REDUCE"`
	DtLiabAdd                    float64 `json:"DT_LIAB_ADD"`
	PredictLiabAdd               float64 `json:"PREDICT_LIAB_ADD"`
	InventoryReduce              float64 `json:"INVENTORY_REDUCE"`
	OperateReceReduce            float64 `json:"OPERATE_RECE_REDUCE"`
	OperatePayableAdd            float64 `json:"OPERATE_PAYABLE_ADD"`
	Other                        float64 `json:"OTHER"`
	OperateNetcashOthernote      float64 `json:"OPERATE_NETCASH_OTHERNOTE"`
	OperateNetcashBalancenote    float64 `json:"OPERATE_NETCASH_BALANCENOTE"`
	NetcashOperatenote           float64 `json:"NETCASH_OPERATENOTE"`
	DebtTransferCapital          float64 `json:"DEBT_TRANSFER_CAPITAL"`
	ConvertBond1Year             float64 `json:"CONVERT_BOND_1YEAR"`
	FinleaseObtainFa             float64 `json:"FINLEASE_OBTAIN_FA"`
	UninvolveInvestfinOther      float64 `json:"UNINVOLVE_INVESTFIN_OTHER"`
	EndCash                      float64 `json:"END_CASH"`
	BeginCash                    float64 `json:"BEGIN_CASH"`
	EndCashEquivalents           float64 `json:"END_CASH_EQUIVALENTS"`
	BeginCashEquivalents         float64 `json:"BEGIN_CASH_EQUIVALENTS"`
	CceAddOthernote              float64 `json:"CCE_ADD_OTHERNOTE"`
	CceAddBalancenote            float64 `json:"CCE_ADD_BALANCENOTE"`
	CceAddnote                   float64 `json:"CCE_ADDNOTE"`
	SalesServicesYoy             float64 `json:"SALES_SERVICES_YOY"`
	DepositInterbankAddYoy       float64 `json:"DEPOSIT_INTERBANK_ADD_YOY"`
	LoanPbcAddYoy                float64 `json:"LOAN_PBC_ADD_YOY"`
	OfiBfAddYoy                  float64 `json:"OFI_BF_ADD_YOY"`
	ReceiveOrigicPremiumYoy      float64 `json:"RECEIVE_ORIGIC_PREMIUM_YOY"`
	ReceiveReinsureNetYoy        float64 `json:"RECEIVE_REINSURE_NET_YOY"`
	InsuredInvestAddYoy          float64 `json:"INSURED_INVEST_ADD_YOY"`
	DisposalTfaAddYoy            float64 `json:"DISPOSAL_TFA_ADD_YOY"`
	ReceiveInterestCommissionYoy float64 `json:"RECEIVE_INTEREST_COMMISSION_YOY"`
	BorrowFundAddYoy             float64 `json:"BORROW_FUND_ADD_YOY"`
	LoanAdvanceReduceYoy         float64 `json:"LOAN_ADVANCE_REDUCE_YOY"`
	RepoBusinessAddYoy           float64 `json:"REPO_BUSINESS_ADD_YOY"`
	ReceiveTaxRefundYoy          float64 `json:"RECEIVE_TAX_REFUND_YOY"`
	ReceiveOtherOperateYoy       float64 `json:"RECEIVE_OTHER_OPERATE_YOY"`
	OperateInflowOtherYoy        float64 `json:"OPERATE_INFLOW_OTHER_YOY"`
	OperateInflowBalanceYoy      float64 `json:"OPERATE_INFLOW_BALANCE_YOY"`
	TotalOperateInflowYoy        float64 `json:"TOTAL_OPERATE_INFLOW_YOY"`
	BuyServicesYoy               float64 `json:"BUY_SERVICES_YOY"`
	LoanAdvanceAddYoy            float64 `json:"LOAN_ADVANCE_ADD_YOY"`
	PbcInterbankAddYoy           float64 `json:"PBC_INTERBANK_ADD_YOY"`
	PayOrigicCompensateYoy       float64 `json:"PAY_ORIGIC_COMPENSATE_YOY"`
	PayInterestCommissionYoy     float64 `json:"PAY_INTEREST_COMMISSION_YOY"`
	PayPolicyBonusYoy            float64 `json:"PAY_POLICY_BONUS_YOY"`
	PayStaffCashYoy              float64 `json:"PAY_STAFF_CASH_YOY"`
	PayAllTaxYoy                 float64 `json:"PAY_ALL_TAX_YOY"`
	PayOtherOperateYoy           float64 `json:"PAY_OTHER_OPERATE_YOY"`
	OperateOutflowOtherYoy       float64 `json:"OPERATE_OUTFLOW_OTHER_YOY"`
	OperateOutflowBalanceYoy     float64 `json:"OPERATE_OUTFLOW_BALANCE_YOY"`
	TotalOperateOutflowYoy       float64 `json:"TOTAL_OPERATE_OUTFLOW_YOY"`
	OperateNetcashOtherYoy       float64 `json:"OPERATE_NETCASH_OTHER_YOY"`
	OperateNetcashBalanceYoy     float64 `json:"OPERATE_NETCASH_BALANCE_YOY"`
	NetcashOperateYoy            float64 `json:"NETCASH_OPERATE_YOY"`
	WithdrawInvestYoy            float64 `json:"WITHDRAW_INVEST_YOY"`
	ReceiveInvestIncomeYoy       float64 `json:"RECEIVE_INVEST_INCOME_YOY"`
	DisposalLongAssetYoy         float64 `json:"DISPOSAL_LONG_ASSET_YOY"`
	DisposalSubsidiaryOtherYoy   float64 `json:"DISPOSAL_SUBSIDIARY_OTHER_YOY"`
	ReducePledgeTimedepositsYoy  float64 `json:"REDUCE_PLEDGE_TIMEDEPOSITS_YOY"`
	ReceiveOtherInvestYoy        float64 `json:"RECEIVE_OTHER_INVEST_YOY"`
	InvestInflowOtherYoy         float64 `json:"INVEST_INFLOW_OTHER_YOY"`
	InvestInflowBalanceYoy       float64 `json:"INVEST_INFLOW_BALANCE_YOY"`
	TotalInvestInflowYoy         float64 `json:"TOTAL_INVEST_INFLOW_YOY"`
	ConstructLongAssetYoy        float64 `json:"CONSTRUCT_LONG_ASSET_YOY"`
	InvestPayCashYoy             float64 `json:"INVEST_PAY_CASH_YOY"`
	PledgeLoanAddYoy             float64 `json:"PLEDGE_LOAN_ADD_YOY"`
	ObtainSubsidiaryOtherYoy     float64 `json:"OBTAIN_SUBSIDIARY_OTHER_YOY"`
	AddPledgeTimedepositsYoy     float64 `json:"ADD_PLEDGE_TIMEDEPOSITS_YOY"`
	PayOtherInvestYoy            float64 `json:"PAY_OTHER_INVEST_YOY"`
	InvestOutflowOtherYoy        float64 `json:"INVEST_OUTFLOW_OTHER_YOY"`
	InvestOutflowBalanceYoy      float64 `json:"INVEST_OUTFLOW_BALANCE_YOY"`
	TotalInvestOutflowYoy        float64 `json:"TOTAL_INVEST_OUTFLOW_YOY"`
	InvestNetcashOtherYoy        float64 `json:"INVEST_NETCASH_OTHER_YOY"`
	InvestNetcashBalanceYoy      float64 `json:"INVEST_NETCASH_BALANCE_YOY"`
	NetcashInvestYoy             float64 `json:"NETCASH_INVEST_YOY"`
	AcceptInvestCashYoy          float64 `json:"ACCEPT_INVEST_CASH_YOY"`
	SubsidiaryAcceptInvestYoy    float64 `json:"SUBSIDIARY_ACCEPT_INVEST_YOY"`
	ReceiveLoanCashYoy           float64 `json:"RECEIVE_LOAN_CASH_YOY"`
	IssueBondYoy                 float64 `json:"ISSUE_BOND_YOY"`
	ReceiveOtherFinanceYoy       float64 `json:"RECEIVE_OTHER_FINANCE_YOY"`
	FinanceInflowOtherYoy        float64 `json:"FINANCE_INFLOW_OTHER_YOY"`
	FinanceInflowBalanceYoy      float64 `json:"FINANCE_INFLOW_BALANCE_YOY"`
	TotalFinanceInflowYoy        float64 `json:"TOTAL_FINANCE_INFLOW_YOY"`
	PayDebtCashYoy               float64 `json:"PAY_DEBT_CASH_YOY"`
	AssignDividendPorfitYoy      float64 `json:"ASSIGN_DIVIDEND_PORFIT_YOY"`
	SubsidiaryPayDividendYoy     float64 `json:"SUBSIDIARY_PAY_DIVIDEND_YOY"`
	BuySubsidiaryEquityYoy       float64 `json:"BUY_SUBSIDIARY_EQUITY_YOY"`
	PayOtherFinanceYoy           float64 `json:"PAY_OTHER_FINANCE_YOY"`
	SubsidiaryReduceCashYoy      float64 `json:"SUBSIDIARY_REDUCE_CASH_YOY"`
	FinanceOutflowOtherYoy       float64 `json:"FINANCE_OUTFLOW_OTHER_YOY"`
	FinanceOutflowBalanceYoy     float64 `json:"FINANCE_OUTFLOW_BALANCE_YOY"`
	TotalFinanceOutflowYoy       float64 `json:"TOTAL_FINANCE_OUTFLOW_YOY"`
	FinanceNetcashOtherYoy       float64 `json:"FINANCE_NETCASH_OTHER_YOY"`
	FinanceNetcashBalanceYoy     float64 `json:"FINANCE_NETCASH_BALANCE_YOY"`
	NetcashFinanceYoy            float64 `json:"NETCASH_FINANCE_YOY"`
	RateChangeEffectYoy          float64 `json:"RATE_CHANGE_EFFECT_YOY"`
	CceAddOtherYoy               float64 `json:"CCE_ADD_OTHER_YOY"`
	CceAddBalanceYoy             float64 `json:"CCE_ADD_BALANCE_YOY"`
	CceAddYoy                    float64 `json:"CCE_ADD_YOY"`
	BeginCceYoy                  float64 `json:"BEGIN_CCE_YOY"`
	EndCceOtherYoy               float64 `json:"END_CCE_OTHER_YOY"`
	EndCceBalanceYoy             float64 `json:"END_CCE_BALANCE_YOY"`
	EndCceYoy                    float64 `json:"END_CCE_YOY"`
	NetprofitYoy                 float64 `json:"NETPROFIT_YOY"`
	AssetImpairmentYoy           float64 `json:"ASSET_IMPAIRMENT_YOY"`
	FaIrDeprYoy                  float64 `json:"FA_IR_DEPR_YOY"`
	OilgasBiologyDeprYoy         float64 `json:"OILGAS_BIOLOGY_DEPR_YOY"`
	IrDeprYoy                    float64 `json:"IR_DEPR_YOY"`
	IaAmortizeYoy                float64 `json:"IA_AMORTIZE_YOY"`
	LpeAmortizeYoy               float64 `json:"LPE_AMORTIZE_YOY"`
	DeferIncomeAmortizeYoy       float64 `json:"DEFER_INCOME_AMORTIZE_YOY"`
	PrepaidExpenseReduceYoy      float64 `json:"PREPAID_EXPENSE_REDUCE_YOY"`
	AccruedExpenseAddYoy         float64 `json:"ACCRUED_EXPENSE_ADD_YOY"`
	DisposalLongassetLossYoy     float64 `json:"DISPOSAL_LONGASSET_LOSS_YOY"`
	FaScrapLossYoy               float64 `json:"FA_SCRAP_LOSS_YOY"`
	FairvalueChangeLossYoy       float64 `json:"FAIRVALUE_CHANGE_LOSS_YOY"`
	FinanceExpenseYoy            float64 `json:"FINANCE_EXPENSE_YOY"`
	InvestLossYoy                float64 `json:"INVEST_LOSS_YOY"`
	DeferTaxYoy                  float64 `json:"DEFER_TAX_YOY"`
	DtAssetReduceYoy             float64 `json:"DT_ASSET_REDUCE_YOY"`
	DtLiabAddYoy                 float64 `json:"DT_LIAB_ADD_YOY"`
	PredictLiabAddYoy            float64 `json:"PREDICT_LIAB_ADD_YOY"`
	InventoryReduceYoy           float64 `json:"INVENTORY_REDUCE_YOY"`
	OperateReceReduceYoy         float64 `json:"OPERATE_RECE_REDUCE_YOY"`
	OperatePayableAddYoy         float64 `json:"OPERATE_PAYABLE_ADD_YOY"`
	OtherYoy                     float64 `json:"OTHER_YOY"`
	OperateNetcashOthernoteYoy   float64 `json:"OPERATE_NETCASH_OTHERNOTE_YOY"`
	OperateNetcashBalancenoteYoy float64 `json:"OPERATE_NETCASH_BALANCENOTE_YOY"`
	NetcashOperatenoteYoy        float64 `json:"NETCASH_OPERATENOTE_YOY"`
	DebtTransferCapitalYoy       float64 `json:"DEBT_TRANSFER_CAPITAL_YOY"`
	ConvertBond1YearYoy          float64 `json:"CONVERT_BOND_1YEAR_YOY"`
	FinleaseObtainFaYoy          float64 `json:"FINLEASE_OBTAIN_FA_YOY"`
	UninvolveInvestfinOtherYoy   float64 `json:"UNINVOLVE_INVESTFIN_OTHER_YOY"`
	EndCashYoy                   float64 `json:"END_CASH_YOY"`
	BeginCashYoy                 float64 `json:"BEGIN_CASH_YOY"`
	EndCashEquivalentsYoy        float64 `json:"END_CASH_EQUIVALENTS_YOY"`
	BeginCashEquivalentsYoy      float64 `json:"BEGIN_CASH_EQUIVALENTS_YOY"`
	CceAddOthernoteYoy           float64 `json:"CCE_ADD_OTHERNOTE_YOY"`
	CceAddBalancenoteYoy         float64 `json:"CCE_ADD_BALANCENOTE_YOY"`
	CceAddnoteYoy                float64 `json:"CCE_ADDNOTE_YOY"`
	OpinionType                  string  `json:"OPINION_TYPE"`
	OsopinionType                string  `json:"OSOPINION_TYPE"`
	MinorityInterest             float64 `json:"MINORITY_INTEREST"`
	MinorityInterestYoy          float64 `json:"MINORITY_INTEREST_YOY"`
}
```
</details> 


<details> <summary> 利润表 lrb</summary>

```
type GincomeData struct {
	Secucode                     string         `json:"SECUCODE"`
	SecurityCode                 string         `json:"SECURITY_CODE"`
	SecurityNameAbbr             string         `json:"SECURITY_NAME_ABBR"`
	OrgCode                      string         `json:"ORG_CODE"`
	OrgType                      string         `json:"ORG_TYPE"`
	ReportDate                   string         `json:"REPORT_DATE"`
	ReportType                   FinaReportType `json:"REPORT_TYPE"`
	ReportDateName               string         `json:"REPORT_DATE_NAME"`
	SecurityTypeCode             string         `json:"SECURITY_TYPE_CODE"`
	NoticeDate                   string         `json:"NOTICE_DATE"`
	UpdateDate                   string         `json:"UPDATE_DATE"`
	Currency                     string         `json:"CURRENCY"`
	TotalOperateIncome           float64        `json:"TOTAL_OPERATE_INCOME"`
	TotalOperateIncomeYoy        float64        `json:"TOTAL_OPERATE_INCOME_YOY"`
	OperateIncome                float64        `json:"OPERATE_INCOME"`
	OperateIncomeYoy             float64        `json:"OPERATE_INCOME_YOY"`
	InterestIncome               interface{}    `json:"INTEREST_INCOME"`
	InterestIncomeYoy            interface{}    `json:"INTEREST_INCOME_YOY"`
	EarnedPremium                interface{}    `json:"EARNED_PREMIUM"`
	EarnedPremiumYoy             interface{}    `json:"EARNED_PREMIUM_YOY"`
	FeeCommissionIncome          interface{}    `json:"FEE_COMMISSION_INCOME"`
	FeeCommissionIncomeYoy       interface{}    `json:"FEE_COMMISSION_INCOME_YOY"`
	OtherBusinessIncome          interface{}    `json:"OTHER_BUSINESS_INCOME"`
	OtherBusinessIncomeYoy       interface{}    `json:"OTHER_BUSINESS_INCOME_YOY"`
	ToiOther                     interface{}    `json:"TOI_OTHER"`
	ToiOtherYoy                  interface{}    `json:"TOI_OTHER_YOY"`
	TotalOperateCost             float64        `json:"TOTAL_OPERATE_COST"`
	TotalOperateCostYoy          float64        `json:"TOTAL_OPERATE_COST_YOY"`
	OperateCost                  float64        `json:"OPERATE_COST"`
	OperateCostYoy               float64        `json:"OPERATE_COST_YOY"`
	InterestExpense              interface{}    `json:"INTEREST_EXPENSE"`
	InterestExpenseYoy           interface{}    `json:"INTEREST_EXPENSE_YOY"`
	FeeCommissionExpense         interface{}    `json:"FEE_COMMISSION_EXPENSE"`
	FeeCommissionExpenseYoy      interface{}    `json:"FEE_COMMISSION_EXPENSE_YOY"`
	ResearchExpense              float64        `json:"RESEARCH_EXPENSE"`
	ResearchExpenseYoy           float64        `json:"RESEARCH_EXPENSE_YOY"`
	SurrenderValue               interface{}    `json:"SURRENDER_VALUE"`
	SurrenderValueYoy            interface{}    `json:"SURRENDER_VALUE_YOY"`
	NetCompensateExpense         interface{}    `json:"NET_COMPENSATE_EXPENSE"`
	NetCompensateExpenseYoy      interface{}    `json:"NET_COMPENSATE_EXPENSE_YOY"`
	NetContractReserve           interface{}    `json:"NET_CONTRACT_RESERVE"`
	NetContractReserveYoy        interface{}    `json:"NET_CONTRACT_RESERVE_YOY"`
	PolicyBonusExpense           interface{}    `json:"POLICY_BONUS_EXPENSE"`
	PolicyBonusExpenseYoy        interface{}    `json:"POLICY_BONUS_EXPENSE_YOY"`
	ReinsureExpense              interface{}    `json:"REINSURE_EXPENSE"`
	ReinsureExpenseYoy           interface{}    `json:"REINSURE_EXPENSE_YOY"`
	OtherBusinessCost            interface{}    `json:"OTHER_BUSINESS_COST"`
	OtherBusinessCostYoy         interface{}    `json:"OTHER_BUSINESS_COST_YOY"`
	OperateTaxAdd                float64        `json:"OPERATE_TAX_ADD"`
	OperateTaxAddYoy             float64        `json:"OPERATE_TAX_ADD_YOY"`
	SaleExpense                  float64        `json:"SALE_EXPENSE"`
	SaleExpenseYoy               float64        `json:"SALE_EXPENSE_YOY"`
	ManageExpense                float64        `json:"MANAGE_EXPENSE"`
	ManageExpenseYoy             float64        `json:"MANAGE_EXPENSE_YOY"`
	MeResearchExpense            interface{}    `json:"ME_RESEARCH_EXPENSE"`
	MeResearchExpenseYoy         interface{}    `json:"ME_RESEARCH_EXPENSE_YOY"`
	FinanceExpense               float64        `json:"FINANCE_EXPENSE"`
	FinanceExpenseYoy            float64        `json:"FINANCE_EXPENSE_YOY"`
	FeInterestExpense            float64        `json:"FE_INTEREST_EXPENSE"`
	FeInterestExpenseYoy         float64        `json:"FE_INTEREST_EXPENSE_YOY"`
	FeInterestIncome             float64        `json:"FE_INTEREST_INCOME"`
	FeInterestIncomeYoy          float64        `json:"FE_INTEREST_INCOME_YOY"`
	AssetImpairmentLoss          interface{}    `json:"ASSET_IMPAIRMENT_LOSS"`
	AssetImpairmentLossYoy       interface{}    `json:"ASSET_IMPAIRMENT_LOSS_YOY"`
	CreditImpairmentLoss         interface{}    `json:"CREDIT_IMPAIRMENT_LOSS"`
	CreditImpairmentLossYoy      interface{}    `json:"CREDIT_IMPAIRMENT_LOSS_YOY"`
	TocOther                     interface{}    `json:"TOC_OTHER"`
	TocOtherYoy                  interface{}    `json:"TOC_OTHER_YOY"`
	FairvalueChangeIncome        interface{}    `json:"FAIRVALUE_CHANGE_INCOME"`
	FairvalueChangeIncomeYoy     interface{}    `json:"FAIRVALUE_CHANGE_INCOME_YOY"`
	InvestIncome                 interface{}    `json:"INVEST_INCOME"`
	InvestIncomeYoy              interface{}    `json:"INVEST_INCOME_YOY"`
	InvestJointIncome            interface{}    `json:"INVEST_JOINT_INCOME"`
	InvestJointIncomeYoy         interface{}    `json:"INVEST_JOINT_INCOME_YOY"`
	NetExposureIncome            interface{}    `json:"NET_EXPOSURE_INCOME"`
	NetExposureIncomeYoy         interface{}    `json:"NET_EXPOSURE_INCOME_YOY"`
	ExchangeIncome               interface{}    `json:"EXCHANGE_INCOME"`
	ExchangeIncomeYoy            interface{}    `json:"EXCHANGE_INCOME_YOY"`
	AssetDisposalIncome          float64        `json:"ASSET_DISPOSAL_INCOME"`
	AssetDisposalIncomeYoy       interface{}    `json:"ASSET_DISPOSAL_INCOME_YOY"`
	AssetImpairmentIncome        float64        `json:"ASSET_IMPAIRMENT_INCOME"`
	AssetImpairmentIncomeYoy     float64        `json:"ASSET_IMPAIRMENT_INCOME_YOY"`
	CreditImpairmentIncome       float64        `json:"CREDIT_IMPAIRMENT_INCOME"`
	CreditImpairmentIncomeYoy    interface{}    `json:"CREDIT_IMPAIRMENT_INCOME_YOY"`
	OtherIncome                  float64        `json:"OTHER_INCOME"`
	OtherIncomeYoy               interface{}    `json:"OTHER_INCOME_YOY"`
	OperateProfitOther           interface{}    `json:"OPERATE_PROFIT_OTHER"`
	OperateProfitOtherYoy        interface{}    `json:"OPERATE_PROFIT_OTHER_YOY"`
	OperateProfitBalance         float64        `json:"OPERATE_PROFIT_BALANCE"`
	OperateProfitBalanceYoy      interface{}    `json:"OPERATE_PROFIT_BALANCE_YOY"`
	OperateProfit                float64        `json:"OPERATE_PROFIT"`
	OperateProfitYoy             float64        `json:"OPERATE_PROFIT_YOY"`
	NonbusinessIncome            float64        `json:"NONBUSINESS_INCOME"`
	NonbusinessIncomeYoy         float64        `json:"NONBUSINESS_INCOME_YOY"`
	NoncurrentDisposalIncome     interface{}    `json:"NONCURRENT_DISPOSAL_INCOME"`
	NoncurrentDisposalIncomeYoy  interface{}    `json:"NONCURRENT_DISPOSAL_INCOME_YOY"`
	NonbusinessExpense           float64        `json:"NONBUSINESS_EXPENSE"`
	NonbusinessExpenseYoy        float64        `json:"NONBUSINESS_EXPENSE_YOY"`
	NoncurrentDisposalLoss       interface{}    `json:"NONCURRENT_DISPOSAL_LOSS"`
	NoncurrentDisposalLossYoy    interface{}    `json:"NONCURRENT_DISPOSAL_LOSS_YOY"`
	EffectTpOther                interface{}    `json:"EFFECT_TP_OTHER"`
	EffectTpOtherYoy             interface{}    `json:"EFFECT_TP_OTHER_YOY"`
	TotalProfitBalance           float64        `json:"TOTAL_PROFIT_BALANCE"`
	TotalProfitBalanceYoy        interface{}    `json:"TOTAL_PROFIT_BALANCE_YOY"`
	TotalProfit                  float64        `json:"TOTAL_PROFIT"`
	TotalProfitYoy               float64        `json:"TOTAL_PROFIT_YOY"`
	IncomeTax                    float64        `json:"INCOME_TAX"`
	IncomeTaxYoy                 float64        `json:"INCOME_TAX_YOY"`
	EffectNetprofitOther         interface{}    `json:"EFFECT_NETPROFIT_OTHER"`
	EffectNetprofitOtherYoy      interface{}    `json:"EFFECT_NETPROFIT_OTHER_YOY"`
	EffectNetprofitBalance       interface{}    `json:"EFFECT_NETPROFIT_BALANCE"`
	EffectNetprofitBalanceYoy    interface{}    `json:"EFFECT_NETPROFIT_BALANCE_YOY"`
	UnconfirmInvestLoss          interface{}    `json:"UNCONFIRM_INVEST_LOSS"`
	UnconfirmInvestLossYoy       interface{}    `json:"UNCONFIRM_INVEST_LOSS_YOY"`
	Netprofit                    float64        `json:"NETPROFIT"`
	NetprofitYoy                 float64        `json:"NETPROFIT_YOY"`
	PrecombineProfit             interface{}    `json:"PRECOMBINE_PROFIT"`
	PrecombineProfitYoy          interface{}    `json:"PRECOMBINE_PROFIT_YOY"`
	ContinuedNetprofit           float64        `json:"CONTINUED_NETPROFIT"`
	ContinuedNetprofitYoy        float64        `json:"CONTINUED_NETPROFIT_YOY"`
	DiscontinuedNetprofit        interface{}    `json:"DISCONTINUED_NETPROFIT"`
	DiscontinuedNetprofitYoy     interface{}    `json:"DISCONTINUED_NETPROFIT_YOY"`
	ParentNetprofit              float64        `json:"PARENT_NETPROFIT"`
	ParentNetprofitYoy           float64        `json:"PARENT_NETPROFIT_YOY"`
	MinorityInterest             float64        `json:"MINORITY_INTEREST"`
	MinorityInterestYoy          float64        `json:"MINORITY_INTEREST_YOY"`
	DeductParentNetprofit        float64        `json:"DEDUCT_PARENT_NETPROFIT"`
	DeductParentNetprofitYoy     float64        `json:"DEDUCT_PARENT_NETPROFIT_YOY"`
	NetprofitOther               interface{}    `json:"NETPROFIT_OTHER"`
	NetprofitOtherYoy            interface{}    `json:"NETPROFIT_OTHER_YOY"`
	NetprofitBalance             interface{}    `json:"NETPROFIT_BALANCE"`
	NetprofitBalanceYoy          interface{}    `json:"NETPROFIT_BALANCE_YOY"`
	BasicEps                     float64        `json:"BASIC_EPS"`
	BasicEpsYoy                  float64        `json:"BASIC_EPS_YOY"`
	DilutedEps                   float64        `json:"DILUTED_EPS"`
	DilutedEpsYoy                float64        `json:"DILUTED_EPS_YOY"`
	OtherCompreIncome            interface{}    `json:"OTHER_COMPRE_INCOME"`
	OtherCompreIncomeYoy         interface{}    `json:"OTHER_COMPRE_INCOME_YOY"`
	ParentOci                    interface{}    `json:"PARENT_OCI"`
	ParentOciYoy                 interface{}    `json:"PARENT_OCI_YOY"`
	MinorityOci                  interface{}    `json:"MINORITY_OCI"`
	MinorityOciYoy               interface{}    `json:"MINORITY_OCI_YOY"`
	ParentOciOther               interface{}    `json:"PARENT_OCI_OTHER"`
	ParentOciOtherYoy            interface{}    `json:"PARENT_OCI_OTHER_YOY"`
	ParentOciBalance             interface{}    `json:"PARENT_OCI_BALANCE"`
	ParentOciBalanceYoy          interface{}    `json:"PARENT_OCI_BALANCE_YOY"`
	UnableOci                    interface{}    `json:"UNABLE_OCI"`
	UnableOciYoy                 interface{}    `json:"UNABLE_OCI_YOY"`
	CreditriskFairvalueChange    interface{}    `json:"CREDITRISK_FAIRVALUE_CHANGE"`
	CreditriskFairvalueChangeYoy interface{}    `json:"CREDITRISK_FAIRVALUE_CHANGE_YOY"`
	OtherrightFairvalueChange    interface{}    `json:"OTHERRIGHT_FAIRVALUE_CHANGE"`
	OtherrightFairvalueChangeYoy interface{}    `json:"OTHERRIGHT_FAIRVALUE_CHANGE_YOY"`
	SetupProfitChange            interface{}    `json:"SETUP_PROFIT_CHANGE"`
	SetupProfitChangeYoy         interface{}    `json:"SETUP_PROFIT_CHANGE_YOY"`
	RightlawUnableOci            interface{}    `json:"RIGHTLAW_UNABLE_OCI"`
	RightlawUnableOciYoy         interface{}    `json:"RIGHTLAW_UNABLE_OCI_YOY"`
	UnableOciOther               interface{}    `json:"UNABLE_OCI_OTHER"`
	UnableOciOtherYoy            interface{}    `json:"UNABLE_OCI_OTHER_YOY"`
	UnableOciBalance             interface{}    `json:"UNABLE_OCI_BALANCE"`
	UnableOciBalanceYoy          interface{}    `json:"UNABLE_OCI_BALANCE_YOY"`
	AbleOci                      interface{}    `json:"ABLE_OCI"`
	AbleOciYoy                   interface{}    `json:"ABLE_OCI_YOY"`
	RightlawAbleOci              interface{}    `json:"RIGHTLAW_ABLE_OCI"`
	RightlawAbleOciYoy           interface{}    `json:"RIGHTLAW_ABLE_OCI_YOY"`
	AfaFairvalueChange           interface{}    `json:"AFA_FAIRVALUE_CHANGE"`
	AfaFairvalueChangeYoy        interface{}    `json:"AFA_FAIRVALUE_CHANGE_YOY"`
	HmiAfa                       interface{}    `json:"HMI_AFA"`
	HmiAfaYoy                    interface{}    `json:"HMI_AFA_YOY"`
	CashflowHedgeValid           interface{}    `json:"CASHFLOW_HEDGE_VALID"`
	CashflowHedgeValidYoy        interface{}    `json:"CASHFLOW_HEDGE_VALID_YOY"`
	CreditorFairvalueChange      interface{}    `json:"CREDITOR_FAIRVALUE_CHANGE"`
	CreditorFairvalueChangeYoy   interface{}    `json:"CREDITOR_FAIRVALUE_CHANGE_YOY"`
	CreditorImpairmentReserve    interface{}    `json:"CREDITOR_IMPAIRMENT_RESERVE"`
	CreditorImpairmentReserveYoy interface{}    `json:"CREDITOR_IMPAIRMENT_RESERVE_YOY"`
	FinanceOciAmt                interface{}    `json:"FINANCE_OCI_AMT"`
	FinanceOciAmtYoy             interface{}    `json:"FINANCE_OCI_AMT_YOY"`
	ConvertDiff                  interface{}    `json:"CONVERT_DIFF"`
	ConvertDiffYoy               interface{}    `json:"CONVERT_DIFF_YOY"`
	AbleOciOther                 interface{}    `json:"ABLE_OCI_OTHER"`
	AbleOciOtherYoy              interface{}    `json:"ABLE_OCI_OTHER_YOY"`
	AbleOciBalance               interface{}    `json:"ABLE_OCI_BALANCE"`
	AbleOciBalanceYoy            interface{}    `json:"ABLE_OCI_BALANCE_YOY"`
	OciOther                     interface{}    `json:"OCI_OTHER"`
	OciOtherYoy                  interface{}    `json:"OCI_OTHER_YOY"`
	OciBalance                   interface{}    `json:"OCI_BALANCE"`
	OciBalanceYoy                interface{}    `json:"OCI_BALANCE_YOY"`
	TotalCompreIncome            float64        `json:"TOTAL_COMPRE_INCOME"`
	TotalCompreIncomeYoy         float64        `json:"TOTAL_COMPRE_INCOME_YOY"`
	ParentTci                    float64        `json:"PARENT_TCI"`
	ParentTciYoy                 float64        `json:"PARENT_TCI_YOY"`
	MinorityTci                  float64        `json:"MINORITY_TCI"`
	MinorityTciYoy               float64        `json:"MINORITY_TCI_YOY"`
	PrecombineTci                interface{}    `json:"PRECOMBINE_TCI"`
	PrecombineTciYoy             interface{}    `json:"PRECOMBINE_TCI_YOY"`
	EffectTciBalance             interface{}    `json:"EFFECT_TCI_BALANCE"`
	EffectTciBalanceYoy          interface{}    `json:"EFFECT_TCI_BALANCE_YOY"`
	TciOther                     interface{}    `json:"TCI_OTHER"`
	TciOtherYoy                  interface{}    `json:"TCI_OTHER_YOY"`
	TciBalance                   interface{}    `json:"TCI_BALANCE"`
	TciBalanceYoy                interface{}    `json:"TCI_BALANCE_YOY"`
	AcfEndIncome                 interface{}    `json:"ACF_END_INCOME"`
	AcfEndIncomeYoy              interface{}    `json:"ACF_END_INCOME_YOY"`
	OpinionType                  string         `json:"OPINION_TYPE"`
}
```
</details> 

<details> <summary> 财务数据 financial</summary>
日期,  
摊薄每股收益(元), 加权每股收益(元), 每股收益_调整后(元), 扣除非经常性损益后的每股收益(元), 
每股净资产_调整前(元), 每股净资产_调整后(元), 
每股经营性现金流(元), 每股资本公积金(元), 每股未分配利润(元), 调整后的每股净资产(元), 

总资产利润率(%), 主营业务利润率(%), 总资产净利润率(%), 成本费用利润率(%), 营业利润率(%), 主营业务成本率(%), 销售净利率(%), 股本报酬率(%), 净资产报酬率(%), 资产报酬率(%), 销售毛利率(%), 

三项费用比重, 非主营比重, 主营利润比重, 股息发放率(%), 投资收益率(%), 

主营业务利润(元), 净资产收益率(%), 加权净资产收益率(%), 扣除非经常性损益后的净利润(元), 主营业务收入增长率(%), 净利润增长率(%), 净资产增长率(%), 总资产增长率(%), 

应收账款周转率(次), 应收账款周转天数(天), 存货周转天数(天), 存货周转率(次), 固定资产周转率(次), 总资产周转率(次), 总资产周转天数(天), 流动资产周转率(次), 流动资产周转天数(天), 股东权益周转率(次), 

流动比率, 速动比率, 现金比率(%), 利息支付倍数, 长期债务与营运资金比率(%), 股东权益比率(%), 

长期负债比率(%), 股东权益与固定资产比率(%), 负债与所有者权益比率(%), 长期资产与长期资金比率(%), 资本化比率(%), 固定资产净值率(%), 资本固定化比率(%), 产权比率(%), 清算价值比率(%), 固定资产比重(%), 资产负债率(%), 总资产(元), 

经营现金净流量对销售收入比率(%), 资产的经营现金流量回报率(%), 经营现金净流量与净利润的比率(%), 经营现金净流量对负债比率(%), 现金流量比率(%),

短期股票投资(元), 短期债券投资(元), 短期其它经营性投资(元), 

长期股票投资(元), 长期债券投资(元), 长期其它经营性投资(元), 

1年以内应收帐款(元), 1-2年以内应收帐款(元), 2-3年以内应收帐款(元), 3年以内应收帐款(元), 1年以内预付货款(元), 1-2年以内预付货款(元), 2-3年以内预付货款(元), 3年以内预付货款(元), 1年以内其它应收款(元), 1-2年以内其它应收款(元), 2-3年以内其它应收款(元), 3年以内其它应收款(元)
</details>