"""Offline, vector mathematical equations; no browser or CDN dependency."""
from io import BytesIO
import json
import re

import matplotlib
matplotlib.use('Agg')
from matplotlib import mathtext
from matplotlib.font_manager import FontProperties


EQUATIONS={
    'observation':r'y_t=\log C_t,\quad y_t=\ell_{j,t}+\epsilon_{j,t},\quad \epsilon_{j,t}\sim N(0,R_j),\quad j\in\{L,F\}',
    'state':r'\ell_{j,t}=\ell_{j,t-1}+b_{j,t-1},\quad b_{j,t}=b_{j,t-1}+\zeta_{j,t},\quad\zeta_{j,t}\sim N(0,\lambda_jR_j)',
    'prior':r'\hat{x}_{j,0}=(y_0,0)^T,\quad P_{j,0}=R_j I,\quad H=(1,0),\quad Q_j=\mathrm{diag}(0,\lambda_jR_j)',
    'predict':r'\hat{x}_t^-=F\hat{x}_{t-1},\quad P_t^-=FP_{t-1}F^T+Q,\quad e_t=y_t-H\hat{x}_t^-,\quad S_t=HP_t^-H^T+R',
    'update':r'K_t=P_t^-H^T/S_t,\quad\hat{x}_t=\hat{x}_t^-+K_te_t,\quad P_t=(I-K_tH)P_t^-',
    'fit_scale':r'\hat{R}(\lambda)=\frac{1}{n}\sum_{t\in\mathcal{T}}\frac{e_t(\lambda)^2}{S_t^{(R=1)}(\lambda)}',
    'fit_ratio':r'\hat{\lambda}=\arg\min_\lambda\frac{1}{2}\sum_{t\in\mathcal{T}}\left[\log(2\pi\hat{R}S_t^{(R=1)})+\frac{e_t^2}{\hat{R}S_t^{(R=1)}}\right]',
    'bounds':r'10^{-10}\leq\lambda_L\leq10^{-6},\qquad10^{-5}\leq\lambda_F\leq10^{-2}',
    'slope_law':r'b_{j,t}\mid y_{0:t}\sim N(\hat{b}_{j,t},v_{j,t}),\quad\delta=0.02\hat{\sigma}_r,\quad r_t=\log(C_t/C_{t-1})',
    'direction':r'p^+_{j,t}=1-\Phi\!\left(\frac{\delta-\hat{b}_{j,t}}{\sqrt{v_{j,t}}}\right),\quad p^-_{j,t}=\Phi\!\left(\frac{-\delta-\hat{b}_{j,t}}{\sqrt{v_{j,t}}}\right),\quad p^0_{j,t}=1-p^+_{j,t}-p^-_{j,t}',
    'interval':r'\mathrm{CI}_{95\%}(b_{j,t})=\hat{b}_{j,t}\pm1.96\sqrt{v_{j,t}},\quad\Delta\hat{b}_{L,t}=\hat{b}_{L,t}-\hat{b}_{L,t-1}',
    'hmm':r'z_t=\hat{b}_{F,t}/\hat{\sigma}_r,\quad S_t\in\{-,0,+\},\quad z_t\mid S_t=s\sim N(\mu_s,\nu),\quad A_{is}=P(S_t=s\mid S_{t-1}=i)',
    'hmm_means':r'-2\leq\mu_-\leq-0.005,\quad\mu_0=0,\quad0.005\leq\mu_+\leq2,\quad\nu\geq10^{-4},\quad0.65\leq A_{ss}\leq0.98',
    'forward':r'\pi_{t,s}=\frac{\phi(z_t;\mu_s,\nu)\sum_i\pi_{t-1,i}A_{is}}{\sum_k\phi(z_t;\mu_k,\nu)\sum_i\pi_{t-1,i}A_{ik}}',
    'buy':r'\mathrm{BUY}_t=\mathbf{1}\{d_{t-1}=0,h_t=0,\mathrm{armed}\}\,\mathbf{1}\{p_t^+\geq\theta_{\rm in}\}\,\mathbf{1}\{\hat{b}_{F,t}>0\},\quad\theta_{\rm in}\in\{0.60,0.75\}',
    'context':r'U_t=\mathbf{1}\{p^+_{L,t}\geq0.70\},\quad\theta_{C,t}=\theta_{\rm out}+(0.85-\theta_{\rm out})U_t,\quad k_{C,t}=k_0(1+U_t)',
    'uniform':r'\theta_{A,t}=\theta_{B,t}=\theta_{\rm out}\in\{0.60,0.75\},\quad k_{A,t}=k_{B,t}=k_0\in\{3,5\}',
    'sell':r'\mathrm{SELL}_t=\mathbf{1}\{d_{t-1}=1\}\,\mathbf{1}\{p_t^-\geq\theta_t\ \mathrm{or}\ (h_t=1,C_t<L_t)\}',
    'trail':r'M_t=\max(O_e,C_e,\ldots,C_t),\quad L_{t+1}=\max\{L_t,M_t-k_t\hat{\sigma}_r O_e\},\quad L_e=O_e(1-k_{t_s}\hat{\sigma}_r)',
    'execution':r'h_t=d_{t-1-\Delta},\quad\Delta\in\{0,1\},\quad f\in\{0.0005,0.001,0.002\}',
    'accounting':r'\Delta\log N_t=h_{t-1}\log\frac{O_t}{C_{t-1}}+h_t\log\frac{C_t}{O_t}-B_t\log(1+f)+E_t\log(1-f)',
    'objective':r'J=0.5u_{\rm full}+0.5\mathrm{median}(u_1,u_2,u_3)-0.25\mathrm{sd}(u_1,u_2,u_3)-0.1\frac{(10-n_{\rm trades})_+}{10}-0.3\frac{(0.2-\bar h)_+}{0.2}',
    'utility':r'u=0.45\,c\!\left(\frac{g-g_{BH}}{0.10}\right)+0.40\,c(S-S_{BH})+0.15\,c(K-K_{BH}),\quad c(x)=\mathrm{clip}(x,-3,3)',
    'old_independent':r'A^{\rm independent}_{(i,j),(k,l)}=P(L_t=k\mid L_{t-1}=i)P(S_t=l\mid S_{t-1}=j)',
    'old_coupled':r'A^{\rm coupled}_{(i,j),(k,l)}=P(L_t=k\mid L_{t-1}=i,S_{t-1}=j)P(S_t=l\mid S_{t-1}=j,L_t=k)',
    'old_observation':r'x_t^{\rm price}=r_t/\hat\sigma_r,\quad x_t^{\rm volume}=(r_t/\hat\sigma_r,\ \log(V_t/V_{t-1})/\hat\sigma_v),\quad\tilde{x}_t=\mathrm{clip}(x_t,-5,5)',
    'old_drift':r'E[\tilde{x}_{t,r}\mid L_t=i,S_t=j]=a_i+b_j,\quad a_-<a_0=0<a_+,\quad b_-<b_0=0<b_+',
    'old_emission':r'\tilde{x}_t\mid L_t=i,S_t=j\sim N\!\left((a_i+b_j,m_{ij,v})^T,\mathrm{diag}(v_r,v_v)\right)',
    'old_context':r'U_t^{\rm old}=\mathbf{1}\{P(L_t=+\mid x_{1:t})\geq0.55\},\quad\theta_t=\theta_0+(0.65-\theta_0)U_t^{\rm old},\quad k_t=k_0(1+U_t^{\rm old})',
    'portfolio':r'w_{i,t}^{\rm overlay}=(0.5+0.5d_{i,t})w_{i,t}^{\rm FR25},\quad\Delta w_{\rm BIL,t}=\sum_{i\ne\rm BIL}(w_{i,t}^{\rm FR25}-w_{i,t}^{\rm overlay})',
    'dynamic':r'\mathrm{adopt}_t=\mathbf{1}\{\|w_t^*-w^{\rm last\ adopted}\|_1\geq0.10\ \mathrm{or\ month\ end}\}',
}


def render_equations(html,out):
    for key,formula in EQUATIONS.items():
        buffer=BytesIO()
        mathtext.math_to_image('$'+formula+'$',buffer,prop=FontProperties(size=17),format='svg',color='#17384d')
        svg=buffer.getvalue().decode('utf-8')
        svg=svg[svg.index('<svg'):]
        # Matplotlib reuses glyph ids across equations; prefix every local id/ref.
        svg=re.sub(r'id="([^"]+)"',lambda m:'id="'+key+'_'+m[1]+'"',svg)
        svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:'xlink:href="#'+key+'_'+m[1]+'"',svg)
        html=html.replace('__EQ_'+key+'__',svg)
    if '__EQ_' in html:raise ValueError('Missing rendered equation')
    (out/'equations.json').write_text(json.dumps(EQUATIONS,indent=2),encoding='utf-8')
    return html


if __name__=='__main__':
    from pathlib import Path
    out=Path(__file__).resolve().parents[1]/'research/latent-slope-20261025-v1'
    out.mkdir(exist_ok=True,parents=True)
    render_equations('',out)
    import matplotlib.pyplot as plt
    for page in range((len(EQUATIONS)+9)//10):
        rows=list(EQUATIONS.items())[page*10:(page+1)*10]
        fig=plt.figure(figsize=(18,len(rows)*.9),layout='constrained')
        axes=fig.subplots(len(rows),1,squeeze=False).ravel()
        for ax,(name,formula) in zip(axes,rows,strict=True):
            ax.axis('off');ax.text(0,.9,name,fontsize=8,color='#617889');ax.text(0,.25,'$'+formula+'$',fontsize=13)
        fig.savefig(out/f'equations-{page+1}.png',dpi=125,bbox_inches='tight');plt.close(fig)
