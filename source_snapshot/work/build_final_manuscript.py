from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = r'''% Self-contained manuscript; empirical values are generated from archived runs.
\documentclass[12pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsthm,booktabs,array}
\usepackage[hidelinks]{hyperref}
\usepackage{xurl}
\usepackage{microtype}
\usepackage{placeins}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\renewcommand{\topfraction}{0.95}
\renewcommand{\bottomfraction}{0.9}
\renewcommand{\textfraction}{0.05}
\renewcommand{\floatpagefraction}{0.75}
\setlength{\emergencystretch}{1em}
\newtheorem{proposition}{Proposition}
\newtheorem{corollary}{Corollary}
\newcommand{\F}{\mathcal{F}}
\newcommand{\R}{\mathbb{R}}
\newcommand{\M}{\mathcal{M}}
\newcommand{\Oset}{\mathcal{O}}
\newcommand{\clip}{\operatorname{clip}}
\title{Auditing Machine-Learning Energy Forecasts with Missing Targets:\\
Sharp Comparisons and Budgeted Recovery}
\author{Jishan Kapoor\\
Independent Researcher\\
Toronto M4Y 1C9, Canada\\
Corresponding author: \href{mailto:kapoorjishan19@gmail.com}{kapoorjishan19@gmail.com}}
\date{}
\begin{document}
\maketitle

\begin{abstract}
@@ABSTRACT@@
\end{abstract}
\noindent\textbf{Keywords:} machine learning; model evaluation; missing targets;
partial identification; active evaluation; energy forecasting.

\section{Introduction}
Evaluating deployed machine-learning models requires verification targets
as well as saved predictions. In energy forecasting, predictions from
artificial intelligence (AI) models can remain available even when the
meter readings needed to evaluate them are incomplete. An analyst comparing two forecasting systems must
then distinguish a performance difference supported by the surviving data
from a difference introduced by the treatment of missing readings. Evaluating
only observed intervals changes the evaluation period. Filling gaps produces
a complete score, but its model ordering can depend on the chosen filling.
This is particularly consequential when an evaluation supports a vendor
comparison, a model-maintenance decision, or a retrospective performance audit.
Neural networks and boosted trees can produce these forecasts, but their
flexibility does not resolve ambiguity in missing verification targets.
The proposed audit operates on their saved predictions and meter constraints;
it does not require retraining or access to model gradients.

This separation of predictions and verification targets is also explicit
in production model monitoring. Azure describes joining logged predictions
to subsequently collected actuals, and Amazon SageMaker documents monitoring
windows for delayed labels \cite{azuremonitor,awsmonitor}. These workflows
motivate evaluation with incomplete targets; they do not establish a
particular energy-audit deadline or the cost of retrieving a missing record.

Cumulative meters provide information that is often discarded by a generic
missing-data workflow. If readings at the endpoints of a gap survive, their
difference constrains the energy consumed within that gap. The relationship
between interval quantities and cumulative register differences is explicit
in Measurement Canada's metering guidance \cite{canada}. The NorPEN data
descriptor documents missing high-frequency transmissions alongside more
reliably collected hourly billing registers \cite{norpen}. These sources
establish an operationally meaningful observation pattern; they do not imply
that an independent backup total is available for every meter or outage.
Elexon's Advanced Data Service procedure specifies reconciliation of
interval sums with cumulative register advances and recovery of a missing
interval from a register advance and the other intervals
\cite{elexon}. This supplies an operational basis for aggregate-constrained
evaluation. Its reconciliation tolerances do not establish physically
exact totals or the six-hour granularity used in our controlled experiment.
The Australian Energy Market Operator's 2026 metrology procedure also
explicitly provides for replacing substituted readings when actual data
are recovered \cite{aemo}. This motivates an audit that can identify which
recoverable records would be most informative for a model comparison.

This paper asks a specific question: \emph{which squared-error comparisons
between fixed interval-energy forecasts follow from incomplete readings and
the retained energy totals alone?} We formulate the unknown verification
targets as a common feasible set. A comparison is established only if every
completion in that set gives the same strict ordering. When the ordering is
unresolved and interval records can be retrieved, we ask which budgeted
batch most reduces the worst remaining comparison ambiguity.

The main algebraic simplification is that the unknown squared target cancels
from a paired squared-error difference. The remaining objective is linear in
the missing energy. With nonnegative targets and disjoint total constraints,
sharp extrema have a closed form and require only a scan of each block. The
interval width has an interpretable decomposition: it depends on missing
energy and variation in the disagreement between forecasts. A high missing
fraction therefore need not imply an uninformative comparison, while a small
gap can matter when the forecasts disagree strongly within it.

The contribution is a constrained model-evaluation and target-recovery method
for energy forecasts
and its completed computational evaluation. It comprises sharp comparison
bounds, attaining witness completions, a characterization of when totals
determine an ordering, and a batch recovery rule that minimizes worst-case
remaining comparison width under a reading budget. A worst-case separation
from greedy allocation and a deterministic adaptivity result characterize the limits of sequential
querying under the same width objective.
The batch method also extends to independently bounded aggregate totals;
a separate implementation and exhaustive solver checks evaluate that
generalization. Appendix~\ref{app:regret} records
the secondary worst-case-regret option and its empirical tradeoffs.
The experiments compare these outputs with deletion,
energy-preserving imputations, and separately bounded individual errors.
They use a client panel, a separate household trace, and actual cumulative
register traces. Outages are imposed retrospectively so that a complete
reference comparison is available. The claims concern verification of the
evaluated record; the method neither improves the original forecasts nor
establishes their relative performance on future observations.

For machine-learning evaluation, the central problem is to distinguish a
model ranking supported by available targets from one induced by an
imputation rule. We propagate the surviving aggregate constraints directly
into the comparison and optimize which additional targets to acquire.
This gives an exact active-evaluation objective for a structured missing-label
problem, with energy forecasting as the evaluated application. It connects
constraint consistency, attainable decision uncertainty, and query allocation
without requiring a new forecasting architecture.

\section{Related Work and Contribution Boundary}
Partial identification formalizes what can be learned without selecting a
single completion of missing information \cite{manski}. Maia Polo et al.
apply this perspective to performance evaluation and model selection under
weak supervision \cite{polo}. Bessac and Naveau study forecast scoring with
imperfect observations using a probabilistic observation model \cite{bessac}.
Botacin and Gomes examine delayed labels and resource constraints in
realistic malware-model evaluation \cite{botacin2025}. Delayed-target
monitoring itself is therefore established context; the present method
addresses sharp finite-record comparisons and minimax-width recovery under
aggregate target constraints.
The abstract of the 2026 road-safety preprint by Elbasri and Elamrani Abou
Elassad (SSRN, \url{https://doi.org/10.2139/ssrn.7176879}) describes
conditional score and model-difference envelopes under changing spatial
units; this literature comparison is limited to its public abstract.
Thus incomplete-outcome evaluation and model-difference
envelopes are established concepts.

Patton \cite{patton} characterizes losses whose expected forecast rankings
are preserved under conditionally unbiased volatility proxies. His loss
representation includes a target-only term that cancels in pairwise
comparisons, leaving affine target dependence. Our squared-loss cancellation
is an instance of this established structure. We instead bound a fixed
historical comparison over every nonnegative completion compatible with
retained energy measurements, then use that feasible set to plan recovery.

Energy-constrained reconstruction also predates this work. Copy-Paste
Imputation (CPI) preserves the total energy of gaps while borrowing shapes
from related observations \cite{cpi}. Hu et al. develop constrained Monte
Carlo disaggregation and uncertainty estimation \cite{hu}. Schaffer et al.
use cumulative information when preparing a large heat-meter dataset
\cite{heat}. These methods aim to construct or sample plausible high-resolution
trajectories. A sampled set of plausible trajectories need not contain the
extrema needed to establish a comparison over \emph{all} measurement-compatible
trajectories.

Our objective is the paired forecast-error difference, rather than the
reconstruction error of an imputed load profile. We retain all completions
allowed by the stated measurements and report exactly which finite-record
comparisons survive that ambiguity. The direct paired calculation is also
compared with separately bounded individual errors, so the empirical benefit
of respecting the shared unknown target can be assessed.

Appendix~\ref{app:regret} applies the standard minimax-regret criterion
\cite{savage,manskiregret} to these bounds as a secondary decision option.
We do not claim to introduce partial identification, minimax regret, linear
optimization, conservation constraints, or a forecasting architecture. The
specific contribution is their specialization to retained meter totals,
including sharp formulas, a useful identifiability diagnostic, an exact
budgeted batch-recovery rule, and evidence about the resulting audit decisions.

@@RECOVERY_RELATED@@

The retained-coefficient subproblem is a one-dimensional minimum-diameter
subset problem, within the classical family studied by Aggarwal et al.
\cite{aggarwal}. Neither this sorting subproblem nor dynamic programming
is claimed as new. The specialized result is the reduction of worst-case
comparison uncertainty after record recovery to this tractable structure,
its exact allocation across retained-total blocks, and its deterministic
adaptivity characterization under the stated information model.

\section{Observation Model and Evaluation Target}
\subsection{Fixed forecasts and a common record}
Let $p^{(j)}\in\R^N$ be the predictions of candidate $j$ for the same $N$
scheduled interval-energy targets. Predictions are issued before these
targets occur and are frozen before evaluation masks are imposed. The
finite-record mean squared error (MSE) is
\begin{equation}
 L_j(y)=\frac{1}{N}\sum_{i=1}^N(p_i^{(j)}-y_i)^2.
 \label{eq:loss}
\end{equation}
All candidates use identical targets and the same denominator. The primary
unit is kWh per interval, so the loss is in kWh$^2$. Equal-weight root mean
squared error (RMSE) has
the same ordering as MSE on this common record, although its numerical
difference is not the MSE difference bounded below.

We condition on a declared evaluator-access regime and treat forecast
vectors as fixed. The primary \emph{restricted-record} regime supplies
the current evaluation record's predictions, observed targets and totals;
it does not supply later forecast records or retained feature caches.
Any target reconstructed from additional authorized records must first be
added to the observed set. Section~\ref{sec:archive-access} evaluates this
augmentation using all available saved test persistence forecasts.
Sharpness and recovery optimality below are relative to the resulting
information set, not every record held anywhere in a forecasting system.

The observed coordinates $\Oset$ have fixed recorded values $o_i$.
The remaining coordinates $\M$ are unavailable to the evaluator.
Disjoint register blocks $I_g$ have retained total-energy constraints
$T_g^-\leq\sum_{i\in I_g}y_i\leq T_g^+$. The total may include both
observed and missing coordinates. In the primary model,
\begin{equation}
 \F=\left\{y:\begin{array}{l}
 y_i=o_i\ (i\in\Oset),\quad y_i\geq0\ (i\in\M),\\
 T_g^-\leq\sum_{i\in I_g}y_i\leq T_g^+\quad\forall g
 \end{array}\right\}.
 \label{eq:feasible}
\end{equation}
Every missing coordinate belongs to exactly one block with a finite upper
total. Nonnegativity and these totals make $\F$ bounded. This default needs
no maximum load estimated from the training data and imposes no smoothness
assumption on a missing load shape.

\subsection{Counter semantics and feasibility}
For missing indices $\M_g=I_g\cap\M$, subtract the surviving interval
energies before optimization:
\begin{align}
 r_g^-&=T_g^- -\sum_{i\in I_g\cap\Oset}o_i,\\
 r_g^+&=T_g^+ -\sum_{i\in I_g\cap\Oset}o_i,\\
 \ell_g&=\max(0,r_g^-),\qquad u_g=r_g^+.
 \label{eq:residual}
\end{align}
If $\ell_g>u_g$, the information is inconsistent and the method returns a
data-quality failure. A block with no missing values must likewise have its
known sum inside its supplied total interval. These are exact-arithmetic
feasibility conditions. The reference API rejects infeasibility; the
experimental pipeline's roundoff convention is specified below and is
distinct from uncertainty in a physical measurement.

An exact total is defensible for differences of retained readings of the
same monotone cumulative counter when the targets are the intervening
counter increments. This is a statement about the recorded counter scale,
not about an error-free measurement of physical energy. Integrating a few
instantaneous power samples does not in general produce exactly the same
quantity. Counter resets, rollover, unit mismatches, import/export mixing,
and timestamp mismatch must be checked before applying the constraints.
The primary experiments use nonnegative consumption. Signed net exchange
requires an appropriate signed feasible set and cannot automatically inherit
the nonnegative formulas.

Where the retained total has a defensible uncertainty range, its interval
is applied before subtracting observed values. If the observed interval
values themselves are uncertain, treating them as exact is inappropriate;
their uncertainty must also be included in $\F$. The 1\% and 5\% ranges
used below are controlled sensitivity settings, not estimated meter-error
distributions or claimed metrological specifications.

\section{Sharp Comparisons and Decision Guarantees}
\subsection{Cancellation of the unknown quadratic term}
For two fixed forecasts $a,b$, put $D(y)=L_a(y)-L_b(y)$. Expanding gives
\begin{align}
 D(y)&=K+\sum_{i\in\M}c_i y_i,\label{eq:linear}\\
 c_i&=\frac{2(b_i-a_i)}{N},\\
 K&=\frac{\sum_{i=1}^N(a_i^2-b_i^2)
       +2\sum_{i\in\Oset}(b_i-a_i)o_i}{N}.
\end{align}
The $y_i^2$ terms cancel because both forecasts are evaluated against the
same unknown truth. All observed contributions and all scheduled targets
remain in the calculation.

\begin{proposition}[Sharp bounds from exact totals]
Suppose $\F$ is nonempty and each nonempty missing block has an exact
residual total $E_g\geq0$. Then the attainable range of $D$ is exactly
$[D^-,D^+]$, where
\begin{align}
 D^-&=K+\sum_g E_g\min_{i\in\M_g}c_i,\label{eq:sharpmin}\\
 D^+&=K+\sum_g E_g\max_{i\in\M_g}c_i.
 \label{eq:sharp}
\end{align}
Blocks with no missing coordinates contribute zero to these sums.
\end{proposition}
\begin{proof}
For $E_g>0$, $\sum_i c_i y_i/E_g$ is a convex combination of the
coefficients in block $g$. Its minimum and maximum are attained by placing
the whole residual energy on an index with the smallest or largest
coefficient. For $E_g=0$, nonnegativity forces every missing value to zero.
Disjoint blocks permit simultaneous attainment of these extrema. Convexity
of $\F$ and linearity of $D$ imply attainment of every intermediate value.
\end{proof}

Thus $D^+<0$ establishes that $a$ has smaller MSE for every admissible
completion, while $D^->0$ establishes that $b$ does. Otherwise a strict
ordering does not follow from these constraints. If $D^-<0<D^+$,
the two extremal completions explicitly demonstrate opposite orderings.
An interval touching zero may establish a weak ordering but does not
establish a strict winner. The implementation conservatively labels such
cases unresolved.

In exact arithmetic, sharpness also establishes completeness of this
strict-decision rule.
If $0\in[D^-,D^+]$, the feasible set contains a tie, so no rule whose
strict winner must be valid for every member of the same feasible set can
certify a strict winner. If the interval straddles zero, opposite winners
are feasible as well. Thus stronger guaranteed decisions require additional
information or additional assumptions, rather than a different treatment
of the same unconstrained missing shape. The recovery method below adds
information by retrieving selected values.

\subsection{Why some gaps are informative and others are not}
\begin{corollary}[Width and identified contrasts]
For exact residual totals,
\begin{equation}
 D^+-D^- = \frac{2}{N}\sum_g E_g
 \left[\max_{i\in\M_g}(b_i-a_i)
       -\min_{i\in\M_g}(b_i-a_i)\right].
 \label{eq:width}
\end{equation}
For a positive-energy block, its contribution vanishes precisely when
the forecast contrast is constant across its missing coordinates.
\end{corollary}
The corollary follows by subtracting the two sharp bounds. It explains why
an audit cannot be characterized by its missing fraction alone. A constant
bias adjustment can be evaluated from the aggregate even if all intervals
within that block are absent. A shape-changing adjustment may remain
unresolved. A block with only one missing value is reconstructed exactly
by its total. In the two-target scenarios, fine aggregate blocks can
therefore reconstruct the missing truth. The six- and twelve-target
conditions also test multiple missing coordinates within a retained block;
resolution in these conditions is important when assessing usefulness
beyond single-value reconstruction.

More generally, for the missing-target set
$\F_{\M}=\{x\geq0:Ax=e\}$, any coefficient vector
$c=A^\top\lambda$ gives a fixed contrast $c^\top x=\lambda^\top e$.
The necessary and sufficient condition is that $c$ is orthogonal to
$\operatorname{span}(\F_{\M}-\F_{\M})$. Equivalence to membership in the row space
of $A$ requires that feasible variations span its null space, as occurs
when a strictly positive feasible point exists. A zero-energy block can
fix coordinates and must not be used to claim the unqualified converse.

Refining a retained total into compatible sub-block totals or recovering
additional true readings shrinks $\F$, so sharp comparison intervals cannot
widen. This is a direct consequence of optimizing over nested sets.

\subsection{Uncertain totals and optional physical limits}
For a nonempty missing block with residual sum in $[\ell_g,u_g]$, let
$c_g^{\min}$ and $c_g^{\max}$ denote the minimum and maximum coefficient.
Its exact contributions become
\begin{align}
 d_g^-&=\min(\ell_g c_g^{\min},u_g c_g^{\min}),\\
 d_g^+&=\max(\ell_g c_g^{\max},u_g c_g^{\max}).
 \label{eq:tolerance}
\end{align}
These replace the block terms in \eqref{eq:sharpmin} and \eqref{eq:sharp}. The coefficient scan
and scalar endpoint choice remain linear in the number of missing values.

Documented coordinate bounds $l_i\leq y_i\leq h_i$ can tighten the result.
For this extension, initialize at $l$, sort coefficients increasingly, and
allocate the mandatory residual energy to the smallest coefficients subject
to capacity. Allocate any optional energy only where the coefficient is
negative. Negating the coefficients gives the maximum. The cost is
$O(m_g\log m_g)$ per block. With bounded coordinates and an uncertain total,
the optimum can use an interior total; evaluating just two fixed-total
solutions is not a valid general replacement for this procedure.
Overlapping aggregate constraints require a general linear program instead
of independent block allocation. The primary study uses no capacity bounds.

Fixed nonnegative loss weights satisfying $\sum_i w_i>0$ are accommodated by replacing $1/N$ with
$w_i/\sum_k w_k$ in each summand. If the target is average power with
unequal interval durations $d_i$, transform $x_i=d_i y_i$ in the energy
constraint; the linear objective coefficient for $x_i$ is then
$2w_i(b_i-a_i)/(d_i\sum_k w_k)$. Merely sorting the unadjusted coefficients
would solve a different problem. Our experiments forecast interval energy
directly.

\subsection{Why separate error bounds can be weaker}
Let $l_a,u_a$ and $l_b,u_b$ be sharp individual loss bounds on the same
$\F$. Independent subtraction gives $[l_a-u_b,u_a-l_b]$, which contains
the direct paired interval. It may combine two extremal completions that
cannot simultaneously be the truth.

For example, take $a=(1,1)$, $b=(2,2)$, and unknown nonnegative
$y_1+y_2=2$. The individual MSE ranges are $[0,1]$ and $[1,2]$, giving
an independent difference interval $[-2,0]$. The paired difference is
exactly $-1$, so the direct method establishes the strict ordering.
Conversely, with $a=(0,2)$ and $b=(2,0)$ under the same total, the
paired difference spans $[-4,4]$; no strict winner can be justified.
These are analytical examples, not experimental measurements.

For completeness, the individual squared-error minimum over a nonnegative
simplex is obtained by Euclidean projection of the prediction vector onto
that simplex. The maximum is attained at a vertex. For exact residual
energy $E$ and missing prediction vector $p$,
\begin{align}
 s^-&=\|p-\Pi_{\Delta(E)}(p)\|_2^2,\\
 s^+&=\sum_i p_i^2+E^2-2E\min_i p_i,
 \label{eq:separate}
\end{align}
where $\Delta(E)=\{x\geq0:\sum_i x_i=E\}$. These standard calculations
provide the same-information comparator in the experiments. For uncertain
totals the minimizing total is
$\clip(\sum_i\max(p_i,0),\ell,u)$; the maximum is the larger endpoint
value of the convex quadratic in \eqref{eq:separate}.

\section{Budgeted Recovery of Missing Readings}
@@RECOVERY_METHOD@@

@@INTERVAL_RECOVERY@@

\section{Experimental Design}
@@DATA_METHODS@@

\subsection{Forecasts and information cutoffs}
The four candidates are previous-day persistence, ridge regression,
histogram gradient boosting, and a multilayer perceptron (MLP) neural
network. Boosting and the MLP provide nonlinear AI models; persistence and
ridge provide simple references. Each forecast supplies all 24 targets at
the start of a day. In this retrospective benchmark, issue time is a
simulated historical day-start cutoff enforced through feature timestamps;
these are not contemporaneously logged vendor forecasts.
Features for target hour $h$ are lagged values at 24, 48, and 168 hours,
the mean of the previous day, and sine/cosine encodings of hour, weekday,
and month. All features are available at the common issue time. The
regression models share parameters across the 24 target hours.

Ridge uses training-only standardization and regularization parameter 1.
Gradient boosting uses 100 iterations, learning rate 0.08, at most 15
leaves, minimum leaf size 20, $L_2$ regularization 1, 127 bins, and seed
1729. The MLP has two hidden layers of 32 and 16 rectified-linear units,
Adam optimization, learning rate 0.001, $L_2$ penalty 0.001, minibatches
of 256, and at most @@MLP_EPOCH_CAP@@ epochs, with seed 1729. Its features are standardized
using training data only; targets are divided by the training mean and
predictions are rescaled to kWh. Validation-based early stopping is disabled;
the library's training-loss convergence rule remains enabled. The supplement
records iterations, final training losses, fit times, and warnings for every
meter. Negative predictions are clipped to zero. The configurations are
fixed before the final evaluation run; no search on its evaluation outcomes is
performed. Training periods,
data-quality filters, and the experiment protocol are stored with the
reproduction code. Forecasts are generated once and reused for every
verification scenario. The experiment isolates missing \emph{verification}
targets, not damaged inputs at forecast issue time.

\subsection{Missingness and retained totals}
For each eligible 24-target record we remove exactly 2, 6, or 12 targets.
The mechanisms are a contiguous gap with a random start, a random scattered
set, and the highest-demand targets. The last is an oracle stress test of
selective missingness, not an estimated mechanism of real communication
failure. Disjoint 6-hour and 24-hour totals are retained. These alternatives
use the same masks within each mechanism, record, and seed. Three seeds
are used for stochastic masks. The deterministic high-demand condition is
not treated as additional independent evidence when repeated in the design.

The exact-total setting is augmented by symmetric uncertainty intervals of
1\% and 5\% of each complete aggregate. Bounds use the widened feasible
set; point-imputation comparators continue to use the central supplied
total. This isolates sensitivity to uncertainty in the surviving totals.
All methods see the same surviving interval values. No learned load cap,
smoothness constraint, or hidden high-resolution target is supplied to an
imputer or bound calculation.

\subsection{Comparators and decisions}
The direct paired bounds are compared with sharp individual MSE bounds
combined by independent subtraction. Both methods can decline to establish
a strict ordering. The point-evaluation comparators are complete-case
scoring, uniform allocation of missing energy, allocation in proportion to
a weekday/hour profile estimated from training data, and an energy-rescaled
historical donor selected using surviving target coordinates. The donor
comparator is inspired by the energy-preservation principle of CPI
\cite{cpi}; it is not presented as a reproduction of CPI's complete
published algorithm. Training-based shapes are independent of the competing
test forecasts. If a shape has zero mass on a missing block, uniform
allocation supplies the fallback.

Each energy-preserving filling subtracts the observed consumption from
the retained total, then distributes that residual over missing intervals.
The complete reference is used only for evaluation of the resulting
ordering and regret. Complete-case scoring uses its common observed-count
denominator; only its ordering is compared with the full-record target.
Its numerical loss magnitude is not substituted for a full-day MSE.

For each pair, a decision is correct if its strict sign agrees with the
complete-reference MSE difference. We report the proportion of comparisons
resolved and errors among those decisions, together with the rate of
unresolved comparisons. A method can achieve zero decision errors by
always declining, so resolution is essential. The minimax rule and
point-imputation selectors also choose a candidate from all four models.
Their realized regret is measured against the best of those four on the
complete reference, and the minimax upper bound is checked separately.
For comparisons across load scales, realized regret and its bound are
divided by the squared training-period mean hourly energy of that meter.
The reported mean is first calculated within each meter and then averaged
across meters. The tail summary is the mean of the meters' individual
95th percentiles, rather than a pooled 95th percentile.

@@PERIOD_ARCHIVE_DESIGN@@

@@RECOVERY_DESIGN@@

@@REVIEW_DESIGN@@

\subsection{Uncertainty, numerical checks, and reproducibility}
The interval $[D^-,D^+]$ is an identification interval for a fixed record,
not a statistical confidence interval. The main panel summaries average
over meters; repeated masks, model pairs, and days are not counted as
independent households. Descriptive 95\% bootstrap intervals resample
entire panel meters 2,000 times, preserving within-meter dependence. The
small external cohorts are reported separately. The ordered meter selection
is a convenience sample, so these intervals describe stability within this
panel rather than population sampling uncertainty. Resampling individual
meters does not account for shared cross-meter shocks. Neither bootstrap ranges
nor deterministic identification bounds establish future forecasting
superiority.

The standard-library reference implementation returns both bounds and
attaining completions. Tests include exhaustive comparison with 250
small integer polytopes, uncertain totals with an interior optimum under
caps, feasibility failures, weighted losses, and refinement monotonicity.
The vectorized experimental implementation is checked against the reference
solver on 1,000 randomly selected feasible comparisons. In the experimental
pipeline, a negative residual total with magnitude at most
$10^{-9}\max(1,|T_g|)$ is clipped to zero; larger negative residuals are
rejected. The recovery interface also accepts a fully observed block only
when the absolute total discrepancy is within that tolerance. This
roundoff convention is separate from the strict reference API, the
measurement-uncertainty intervals, and the decision margin. It is not a
license to repair inconsistent physical measurements. Numerical decisions
use a margin of $10^{-9}\max(1,|D^-|,|D^+|)$ in the study's stated loss
scale. These are floating-point computations, not a formally verified
interval-arithmetic implementation. The mathematical propositions concern
real arithmetic; the numerical margin avoids decisions close to zero.

Further integration tests check forecast-feature causality,
daylight-saving exclusions, 100 random linear-program comparisons, and
invariance to replacing hidden targets while preserving all evaluator-visible
values and totals. An independently implemented computational check compares 1,800 paired
extrema against a general linear-programming solver and 600 individual
minima against constrained numerical optimization. Here independence means
different checker implementations and optimization algorithms within the
same study; it does not mean verification by an external investigator.
These checks supplement
the proofs and do not substitute for the experimental resolution results.
Regression tests additionally cover nonfinite inputs, inconsistent totals,
negative consumption, array-shape mismatches, and cancellation at large
common offsets. Objective values are evaluated from differences of prediction
residuals at attaining completions, avoiding the subtraction of large
squared forecasts. This improves numerical stability but does not convert
floating-point computations into formal interval arithmetic.

@@NUMERICAL_SCALE@@

All scenarios, including unresolved outcomes and unfavorable comparator
results, are retained. Data-source identifiers and hashes, meter IDs, splits,
forecast-file checksums and regeneration code, per-meter scenario summaries,
package versions, and the
protocol are included in the reproducibility materials. Forecast and data
preparation costs are distinguished from the calculation of the comparison
bounds.

@@ARCHIVE_DESIGN@@

@@HOLDOUT_DESIGN@@

@@INTERVAL_TRACE_DESIGN@@

\subsection{Generative-AI assistance}
OpenAI Codex was used for literature discovery, mathematical review,
code development, execution support, and drafting. Numerical evidence was
obtained by executing the archived experimental and validation scripts;
language-model responses were not treated as experimental measurements.
The independent optimization checks and finite exhaustive tests described
above audit the numerical implementations. This assistance is separate
from the MLP and boosted-tree models evaluated as forecasting candidates.

\section{Results}
@@RESULTS@@

\section{Discussion}
@@DISCUSSION@@

\subsection{Operational interpretation}
The method supplies an auditable answer to a narrow operational question:
whether the surviving measurements establish the better forecast on a
specified historical record. Its inputs are archived predictions, available
interval readings, and validated aggregate constraints. Its outputs are a
comparison interval, an ordering if justified, and witness completions
showing the limits of the evidence. A model comparison that changes sign
across these witnesses cannot be made robust merely by reporting more
decimal places in an imputed score.

For an audit performed at a specific cutoff, the evaluated target window
must already be complete and the available predictions, targets, aggregates
and reconstructive records must be declared with provenance. Later artifacts
cannot be used before they are available. This study records simulated
forecast issue cutoffs, but has no production arrival or repair timestamps;
it therefore does not establish a decision-latency advantage.

A deployment can follow four explicit steps. First, archive the issued
AI forecasts and align their target intervals with validated surviving
readings and register endpoints. Include any values reconstructable from
retained feature caches or later forecast records when provenance verifies
that they preserve actual measurements. For example, a later persistence
forecast can directly reveal an earlier reading if its input was the actual
measurement rather than an imputation. Second, reject inconsistent totals and
compute the sharp comparison interval. Third, if the ordering is unresolved
and records are recoverable, allocate the allowed validation budget using
the sorted-window dynamic program. Fourth, retrieve and validate those
records, update the residual totals, and recompute the comparison. An
unresolved result remains an explicit outcome rather than a forced winner.
The equal-cost budget describes selective record retrieval and validation;
whether that abstraction saves work relative to recovering the entire gap
must be established in the intended metering system. If an archive returns
an entire gap in one inexpensive request, minimizing individual readings
may offer no material retrieval saving. The reported budget measures
records to retrieve and validate, not packets, staff time, or monetary cost.
The Elexon procedures motivate the availability and subsequent correction
of aggregate-constrained records, but do not validate this complete
machine-learning audit or its equal-cost query model. Access restrictions
must also permit the requested recovery; a missing consent to use interval
data is not authorization to retrieve it.

A prospective policy that repeatedly selects tomorrow's
forecaster from yesterday's incomplete audit would be a separate study.
No dispatch savings, financial benefit, or reliability improvement is
inferred from the verification results here.

\subsection{Limitations and scope}
The comparison bounds intentionally allow extreme missing load shapes.
This can produce wide intervals, especially for long gaps and coarse
totals. It is the price of avoiding an unvalidated shape model. Genuine
physical limits could narrow the set, but the observed training maximum
does not provide a guaranteed capacity bound. The guarantees remain
conditional on the declared feasible set.

The experiments impose missingness retrospectively. Actual cumulative
register traces test the arithmetic of retained endpoint constraints, but
they do not establish the frequency with which independent backup totals
survive field outages. Complete-record eligibility also conditions away
some of the most difficult real episodes. The small cumulative-register
cohort supplies a concrete application rather than a population estimate.
The six- and twelve-hour outages are controlled stress conditions, not
estimates of a typical outage duration. In particular, NorPEN's reported
short high-frequency transmission gaps do not establish that such long
hourly gaps are common.
The fixed forecasters span several standard approaches, but the results
need not transfer unchanged to every load population or candidate set.
The MLP is a fixed, small neural network for reproducible CPU evaluation;
the study does not establish state-of-the-art forecasting accuracy. The
historical sources support controlled comparisons, while contemporary
field validation remains a separate requirement for deployment claims.
The original daily experiments use their frozen supplied-input protocol.
The corrected whole-period audit instead incorporates every documented
direct persistence copy in the permitted saved test archive before
evaluation; its restricted reference aggregates isolated daily summaries.
The sharpness claim is relative to each explicitly declared feasible set.
Neither analysis imposes inverse constraints from the other fitted models
(including ridge), uses retained feature caches,
or accesses unsaved records. The period reanalysis and interval-total
recovery experiment were specified after review on the original panel;
they are sensitivity analyses, not additional independent cohorts.
The tolerance bands are imposed around recorded totals and do not estimate
instrument calibration errors. A field evaluation must establish the actual
information boundary and the cost of acquiring the remaining records.

Squared-error cancellation is central to the simple formulas. Other losses
may require different optimization, and an MSE certificate should not be
relabelled as an MAE or probabilistic-score certificate. Overlapping totals,
correlated counter errors, and signed flows require appropriately richer
constraints. The proofs establish sharpness relative to the supplied set;
they do not validate the measurement model itself.

\FloatBarrier
\section{Conclusion}
@@CONCLUSION@@

\FloatBarrier
\appendix
\section{Conservative Selection When Ordering Is Unresolved}\label{app:regret}
Let $U_{jk}=\max_{y\in\F}(L_j(y)-L_k(y))$, with $U_{jj}=0$.
For a finite set of fixed candidates define
\begin{equation}
 R_j=\max_{y\in\F}\{L_j(y)-\min_k L_k(y)\}.
 \label{eq:regret}
\end{equation}
The comparator is the best member of this candidate set for the completed
record. It is not a forecast that had advance access to the targets.
\begin{proposition}[Regret from pairwise bounds]
For a common nonempty compact feasible set,
\begin{equation}
 R_j=\max_k U_{jk},\qquad
 j^*\in\arg\min_j\max_k U_{jk}.
 \label{eq:minimax}
\end{equation}
Consequently, $j^*$ minimizes the worst-case empirical regret among the
available candidates.
\end{proposition}
\begin{proof}
$L_j(y)-\min_kL_k(y)=\max_k(L_j(y)-L_k(y))$.
Taking a maximum over $y$ commutes with the finite maximum over $k$.
Both sides optimize over the same product of the feasible set and candidate
index set. No interchange of a minimum and a maximum is required.
\end{proof}
For every $y\in\F$, the selected candidate's realized regret is at most
$R_{j^*}$. This guarantee is conditional on the measurement constraints
containing the relevant truth. It does not imply that the minimax choice
has the smallest regret at every particular completion. An imputation-based
choice can perform better at the actual reference record; both realized
regret and the worst-case bound are therefore evaluated.


@@REGRET_RESULTS@@


\FloatBarrier
\section*{Supplementary Materials}
\textbf{Online Resource 1: Reproducibility package.}
The accompanying \texttt{research\_supplement.zip} contains implementations,
source-download and reproduction scripts, dated protocols, aggregate
results, frozen fitted-model forecasts, validation reports, and the
manuscript reconstruction scripts.

\section*{Statements and Declarations}
\subsection*{Data and Code Availability}
The source datasets are publicly identified in References
\cite{uci,portugal,blem}. Reproduction code, the documented protocol and its
dated amendments, complete scenario summaries, and
validation results accompany this manuscript as supplementary materials.
The supplement identifies exact source versions and checksums and recreates
the hourly targets from the original sources. The original fitting pipeline
is supplied separately from the no-refit evaluation reproduction.
\texttt{frozen\_forecasts.csv} supplies saved fitted-model forecasts for all
34 series, target timestamps, and simulated issue-time cutoffs; it also
includes persistence for the two UCI sources. BLEM persistence is omitted
because it directly copies earlier raw readings and can be regenerated.
For exact reproduction, \texttt{review\_frozen\_forecasts.csv} preserves
the original fitted-forecast text and the UCI targets, with only BLEM
targets and persistence omitted. Combining this lossless export with the
pinned raw targets restores all 89,496 original evaluation rows to the
original byte-level SHA-256 checksum without refitting. That reconstruction
has been executed; the supplied \texttt{--raw} mode reruns the corrected
analyses from these restored records. The default
\texttt{work/reproduce\_review\_revision.py} command independently checks
distributed UCI period traces and interval aggregates and rebuilds the
manuscript. Its BLEM checks reconcile aggregates; detailed BLEM case
reconstruction requires the full local records or raw mode. Full period
traces, archive-aware case endpoints and old per-day recovery cases that
could reveal omitted BLEM readings are replaced by UCI-only public exports
and omission manifests. Full local and raw-mode period checks cover all
34 series. The default mode does not claim an independent forecast refit
or a raw-data rerun.
The separate UCI-only new-consumer replication supplies its hourly targets
and all four forecasts under the source's CC BY 4.0 terms, with attribution
and preprocessing documented in the supplement.
The full
per-hour prediction/target archive is retained for the local analysis but
omitted from the submission supplement because a separate redistribution
license for the BLEM readings was not verified. Its checksum is recorded
so regenerated files can be checked. No public
repository publication is claimed beyond the cited original data sources.

\subsection*{Research Transparency}
This study reanalyzes public meter records and does not recruit participants
or collect new measurements. Artificial outages, constructed totals,
recorded counter increments, and assumed total-error ranges are distinguished
in the methods. All reported numerical results were calculated by the
accompanying code.

\subsection*{Funding and Competing Interests}
\textbf{Funding.} This research received no external funding.

\textbf{Competing interests.} The author declares no conflicts of interest.

\subsection*{Generative-AI Disclosure}
OpenAI Codex (OpenAI; accessed October 2026) assisted with literature
searches, mathematical review, programming, experimental execution, and
manuscript drafting. This assistance is distinct from the trained MLP and
boosted-tree forecasting models evaluated in the study.

\FloatBarrier
\begin{thebibliography}{99}
\bibitem{azuremonitor} Microsoft, ``Monitor the performance of models deployed
to production,'' Azure Machine Learning documentation, updated 11 February
2026. \url{https://learn.microsoft.com/en-us/azure/machine-learning/how-to-monitor-model-performance?view=azureml-api-2}.
\bibitem{awsmonitor} Amazon Web Services, ``Model Monitor FAQs,'' Amazon
SageMaker AI Developer Guide, accessed 9 October 2026.
\url{https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor-faqs.html}.
\bibitem{botacin2025} M. Botacin and H. Gomes, ``Towards more realistic
evaluations: The impact of label delays in malware detection pipelines,''
\emph{Computers \& Security}, vol.~148, art.~104122, 2025.
\url{https://doi.org/10.1016/j.cose.2024.104122}.
\bibitem{canada} Measurement Canada, ``GEN-31---Policy on multirate register
metering,'' sec.~5.7, revised 2010.
\url{https://ised-isde.canada.ca/site/measurement-canada/en/laws-and-requirements/gen-31-policy-multirate-register-metering}.
\bibitem{norpen} A. Vavouris, F. Guasselli, L. Stankovic, V. Stankovic,
K. Gram-Hanssen, and S. Didierjean, ``Descriptor: A Norwegian positive
energy neighborhood dataset of electrical measurements and interviews on
energy practices (NorPEN),'' \emph{IEEE Data Descriptions}, vol.~1, 2024.
\url{https://doi.org/10.1109/IEEEDATA.2024.3483154}.
\bibitem{elexon} Elexon, ``BSCP702: Advanced Data Service,'' version 2.0,
effective 6 November 2025, secs.~4.2.7A--B, 4.2.16--17, and 4.2.21.
\url{https://bscdocs.elexon.co.uk/bsc-module/bsc-procedures/bscp702-advanced-data-service}.
\bibitem{manski} C. F. Manski, ``Partial identification with missing data:
Concepts and findings,'' \emph{International Journal of Approximate
Reasoning}, vol.~39, pp.~151--165, 2005.
\url{https://doi.org/10.1016/j.ijar.2004.10.006}.
\bibitem{polo} F. Maia Polo, S. Maity, M. Yurochkin, M. Banerjee, and
Y. Sun, ``Weak supervision performance evaluation via partial
identification,'' \emph{Advances in Neural Information Processing
Systems}, vol.~37, 2024. \url{https://arxiv.org/abs/2312.04601}.
\bibitem{bessac} J. Bessac and P. Naveau, ``Forecast score distributions
with imperfect observations,'' \emph{Advances in Statistical Climatology,
Meteorology and Oceanography}, vol.~7, pp.~53--71, 2021.
\url{https://doi.org/10.5194/ascmo-7-53-2021}.
\bibitem{patton} A. J. Patton, ``Volatility forecast comparison using
imperfect volatility proxies,'' \emph{Journal of Econometrics}, vol.~160,
no.~1, pp.~246--256, 2011. \url{https://doi.org/10.1016/j.jeconom.2010.03.034}.

\bibitem{aggarwal} A. Aggarwal, H. Imai, N. Katoh, and S. Suri, ``Finding
$k$ points with minimum diameter and related problems,'' \emph{Journal of
Algorithms}, vol.~12, no.~1, pp.~38--56, 1991,
\url{https://doi.org/10.1016/0196-6774(91)90022-Q}.
\bibitem{cpi} M. Weber, M. Turowski, H. K. \c{C}akmak, R. Mikut,
U. K\"uhnapfel, and V. Hagenmeyer, ``Data-driven copy-paste imputation
for energy time series,'' \emph{IEEE Transactions on Smart Grid},
vol.~12, no.~6, pp.~5409--5419, 2021.
\url{https://doi.org/10.1109/TSG.2021.3101831}.
\bibitem{hu} S. Hu, H. Dai, F. Meng, L. Aslett, M. Pollock, and
G. O. Roberts, ``Statistical disaggregation---A Monte Carlo approach
for imputation under constraints,'' \emph{Scandinavian Journal of
Statistics}, vol.~52, no.~3, pp.~1376--1421, 2025.
\url{https://doi.org/10.1111/sjos.12790}.
\bibitem{heat} M. Schaffer, T. Tvedebrink, and A. Marszal-Pomianowska,
``Three years of hourly data from 3021 smart heat meters installed in
Danish residential buildings,'' \emph{Scientific Data}, vol.~9,
art.~420, 2022. \url{https://doi.org/10.1038/s41597-022-01502-3}.
\bibitem{savage} L. J. Savage, ``The theory of statistical decision,''
\emph{Journal of the American Statistical Association}, vol.~46,
pp.~55--67, 1951. \url{https://doi.org/10.1080/01621459.1951.10500768}.
\bibitem{manskiregret} C. F. Manski, ``Minimax-regret treatment choice
with missing outcome data,'' \emph{Journal of Econometrics}, vol.~139,
pp.~105--115, 2007. \url{https://doi.org/10.1016/j.jeconom.2006.06.006}.
\bibitem{uci} G. Hebrail and A. Berard, ``Individual household electric
power consumption,'' UCI Machine Learning Repository, dataset, 2006.
\url{https://doi.org/10.24432/C58K54}.
\bibitem{portugal} A. Trindade, ``ElectricityLoadDiagrams20112014,''
UCI Machine Learning Repository, dataset, 2015.
\url{https://doi.org/10.24432/C58C86}.
@@BLEM_REFERENCE@@
@@RECOVERY_REFERENCES@@
\end{thebibliography}
\end{document}
'''

if __name__ == '__main__':
    import json
    import re
    sections = json.loads((ROOT/'work/final_sections.json').read_text(encoding='utf-8'))
    text = TEMPLATE
    for key, value in sections.items():
        text = text.replace('@@'+key+'@@', value)
    if '@@' in text:
        raise ValueError('Unfilled manuscript section')
    from integrate_randomized_revision import integrate
    text = integrate(text, ROOT)
    # Number references consecutively in first-citation order.
    opening=r'\begin{thebibliography}{99}'
    front,bibliography=text.split(opening,1)
    body,tail=bibliography.split(r'\end{thebibliography}',1)
    matches=list(re.finditer(r'\\bibitem\{([^}]+)\}',body))
    entries={match.group(1):body[match.start():matches[i+1].start() if i+1<len(matches) else len(body)].strip()
             for i,match in enumerate(matches)}
    order=list(dict.fromkeys(key.strip() for group in re.findall(r'\\cite\{([^}]+)\}',front)
                              for key in group.split(',')))
    if set(order)!=set(entries):
        raise ValueError('Missing or uncited bibliography entries: '+str(set(order)^set(entries)))
    text=front+opening+'\n'+body[:matches[0].start()].strip()+'\n'+'\n'.join(entries[key] for key in order)+'\n'+r'\end{thebibliography}'+tail
    (ROOT/'outputs/revised_manuscript.tex').write_text(text, encoding='utf-8')
