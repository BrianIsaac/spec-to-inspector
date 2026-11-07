# The whole batch's two runs: every value that differs

Made from the records alone, field by field: `first-run.<part>.json` and `<part>.json`, and what the wrapper wrote. A field not listed reads the same in both.

## The boards

| Part | Boards in both | flagged | score | outcome | cited_heading | cited_class | sentence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pcb1 | 200 | 0 | 0 | 0 | 0 | 0 | 0 |
| pcb4 | 201 | 0 | 0 | 0 | 0 | 0 | 0 |

## The whole run's wall clock, the wrapper's

| Step | Run 1, seconds | Run 2, seconds |
| --- | --- | --- |
| the whole run | 633 | 634 |
| pcb1 | 302 | 303 |
| pcb4 | 326 | 326 |

## The fields of each part's record

| Part | Part of the record | Fields | Fields that differ |
| --- | --- | --- | --- |
| pcb1 | Board by board: `observations` | 4188 | 311 |
| pcb1 | Figure 7: `report_seconds`, `whole_seconds` | 2 | 2 |
| pcb1 | Figure 7: `times` | 43 | 23 |
| pcb1 | Figure 8: `inspector` | 4 | 3 |
| pcb1 | Figure 9: `judge_memory` | 8 | 0 |
| pcb1 | Figure 9: `memory` | 24 | 6 |
| pcb1 | How the judge was asked: `judge` | 41 | 3 |
| pcb1 | The anomaly model's stage: `run` | 26 | 3 |
| pcb1 | The boards: `counts` | 7 | 0 |
| pcb1 | The cards and the report: `report` | 12 | 1 |
| pcb1 | The specification: `specification`, `clause_table` | 12 | 1 |
| pcb1 | The void rules: `leak`, `on_threshold`, `refused_answers` | 16 | 0 |
| pcb1 | What the record is made of | 32 | 1 |
| pcb4 | Board by board: `observations` | 4223 | 307 |
| pcb4 | Figure 7: `report_seconds`, `whole_seconds` | 2 | 2 |
| pcb4 | Figure 7: `times` | 43 | 23 |
| pcb4 | Figure 8: `inspector` | 4 | 3 |
| pcb4 | Figure 9: `judge_memory` | 8 | 0 |
| pcb4 | Figure 9: `memory` | 27 | 4 |
| pcb4 | How the judge was asked: `judge` | 41 | 3 |
| pcb4 | The anomaly model's stage: `run` | 26 | 3 |
| pcb4 | The boards: `counts` | 6 | 0 |
| pcb4 | The cards and the report: `report` | 12 | 1 |
| pcb4 | The specification: `specification`, `clause_table` | 12 | 1 |
| pcb4 | The void rules: `leak`, `on_threshold`, `refused_answers` | 46 | 0 |
| pcb4 | What the record is made of | 32 | 1 |

## Board by board: `observations`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `observations[bad-000].areas[1].seconds` | 1.9564195119892247 | 1.9717352020088583 |
| `observations[bad-000].judge_seconds` | 2.002429075015243 | 2.0172988870181143 |
| `observations[bad-001].areas[1].seconds` | 2.364078197046183 | 2.3574479670496657 |
| `observations[bad-001].judge_seconds` | 2.4878189290175214 | 2.484706166025717 |
| `observations[bad-002].areas[1].seconds` | 2.146077459969092 | 2.1480140860076062 |
| `observations[bad-002].judge_seconds` | 2.2532517869840376 | 2.252808842982631 |
| `observations[bad-003].areas[1].seconds` | 2.1238319000112824 | 2.13139819301432 |
| `observations[bad-003].judge_seconds` | 2.241454362985678 | 2.257626916980371 |
| `observations[bad-004].areas[1].seconds` | 2.166037961957045 | 2.18330747197615 |
| `observations[bad-004].judge_seconds` | 2.278492361016106 | 2.2953461530269124 |
| `observations[bad-005].areas[1].seconds` | 2.1214136609924026 | 2.1013108619954437 |
| `observations[bad-005].judge_seconds` | 2.2901066409540363 | 2.2680235419538803 |
| `observations[bad-006].areas[1].seconds` | 2.085235684993677 | 2.08875573403202 |
| `observations[bad-006].judge_seconds` | 2.213669159973506 | 2.221117623965256 |
| `observations[bad-007].areas[1].seconds` | 2.2770970659912564 | 2.270662000984885 |
| `observations[bad-007].judge_seconds` | 2.5050511269946583 | 2.5043298059608787 |
| `observations[bad-008].areas[1].seconds` | 2.0907905980129726 | 2.1029948290088214 |
| `observations[bad-008].judge_seconds` | 2.222736662020907 | 2.2353866340126842 |
| `observations[bad-009].areas[1].seconds` | 2.0710471170023084 | 2.0941174809704535 |
| `observations[bad-009].judge_seconds` | 2.2131130800116807 | 2.240591486042831 |
| `observations[bad-010].areas[1].seconds` | 2.082494065980427 | 2.0648803189978935 |
| `observations[bad-010].judge_seconds` | 2.1830661399872042 | 2.165274811035488 |
| `observations[bad-011].areas[1].seconds` | 2.250419777003117 | 2.245340204972308 |
| `observations[bad-011].judge_seconds` | 2.36233109398745 | 2.357991121010855 |
| `observations[bad-012].areas[1].seconds` | 2.105967288953252 | 2.102521668013651 |
| `observations[bad-012].judge_seconds` | 2.2313724029809237 | 2.2271627869922668 |
| `observations[bad-013].areas[1].seconds` | 2.1503703360212967 | 2.177002820011694 |
| `observations[bad-013].judge_seconds` | 2.29885069798911 | 2.324985184997786 |
| `observations[bad-014].areas[1].seconds` | 2.2665394380455837 | 2.26093824201962 |
| `observations[bad-014].judge_seconds` | 2.5083499060128815 | 2.497163320018444 |
| `observations[bad-015].areas[1].seconds` | 2.2310052539687604 | 2.2351953120087273 |
| `observations[bad-015].judge_seconds` | 2.2782087809755467 | 2.283226902014576 |
| `observations[bad-016].areas[1].seconds` | 2.0644014549907297 | 2.0637711960007437 |
| `observations[bad-016].judge_seconds` | 2.158115121012088 | 2.158346584008541 |
| `observations[bad-017].areas[1].seconds` | 2.0177951540099457 | 2.0263755790074356 |
| `observations[bad-017].judge_seconds` | 2.0652580829919316 | 2.0764113410259597 |
| `observations[bad-018].areas[1].seconds` | 2.226436469994951 | 2.228814730013255 |
| `observations[bad-018].judge_seconds` | 2.270448242954444 | 2.277135303011164 |
| `observations[bad-019].areas[1].seconds` | 2.5660970589960925 | 2.5731814169557765 |
| `observations[bad-019].judge_seconds` | 2.6151916069793515 | 2.6238688779994845 |
| `observations[bad-020].judge_seconds` | 0.0006416529649868608 | 0.0006419720011763275 |
| `observations[bad-021].areas[1].seconds` | 1.9602960740448907 | 1.9713716669939458 |
| `observations[bad-021].judge_seconds` | 2.0351238119765185 | 2.0463346330216154 |
| `observations[bad-022].judge_seconds` | 0.0006063869805075228 | 0.0006888879579491913 |
| `observations[bad-023].areas[1].seconds` | 2.1072530369856395 | 2.111197759048082 |
| `observations[bad-023].judge_seconds` | 2.1675805159611627 | 2.1704914860310964 |
| `observations[bad-024].areas[1].seconds` | 2.107956360967364 | 2.119459812005516 |
| `observations[bad-024].judge_seconds` | 2.156204896979034 | 2.1676522140041925 |
| `observations[bad-025].judge_seconds` | 0.0005971820210106671 | 0.0006260170484893024 |
| `observations[bad-026].areas[1].seconds` | 2.161387210013345 | 2.190828871971462 |
| `observations[bad-026].judge_seconds` | 2.209800685988739 | 2.2434463080135174 |
| `observations[bad-027].areas[1].seconds` | 2.233268128009513 | 2.236676080035977 |
| `observations[bad-027].judge_seconds` | 2.2812728080316447 | 2.28472833102569 |
| `observations[bad-028].areas[1].seconds` | 2.2912447309936397 | 2.3076897879946046 |
| `observations[bad-028].judge_seconds` | 2.350045436003711 | 2.3664926089695655 |
| `observations[bad-029].areas[1].seconds` | 2.172176624997519 | 2.1875472250394523 |
| `observations[bad-029].judge_seconds` | 2.220873846032191 | 2.234446140995715 |
| `observations[bad-030].areas[1].seconds` | 2.2032791480305605 | 2.197337376012001 |
| `observations[bad-030].judge_seconds` | 2.259420143032912 | 2.2509905710467137 |
| `observations[bad-031].areas[1].seconds` | 2.084510099957697 | 2.096309400978498 |
| `observations[bad-031].judge_seconds` | 2.1355472760042176 | 2.144566014991142 |
| `observations[bad-032].areas[1].seconds` | 2.09569513698807 | 2.104828705021646 |
| `observations[bad-032].judge_seconds` | 2.1686488279956393 | 2.1784366340143606 |
| `observations[bad-033].areas[1].seconds` | 1.8369172569946386 | 1.8508482170291245 |
| `observations[bad-033].judge_seconds` | 1.884793183999136 | 1.8972255619592033 |
| `observations[bad-034].areas[1].seconds` | 2.3253601689939387 | 2.3309617349877954 |
| `observations[bad-034].judge_seconds` | 2.369363963021897 | 2.3812495279707946 |
| `observations[bad-035].areas[1].seconds` | 2.2339142749551684 | 2.242082924989518 |
| `observations[bad-035].judge_seconds` | 2.2813564999960363 | 2.289841510995757 |
| `observations[bad-036].areas[1].seconds` | 2.1141975909704342 | 2.1148496760288253 |
| `observations[bad-036].judge_seconds` | 2.1625869409763254 | 2.1655453339917585 |
| `observations[bad-037].judge_seconds` | 0.0001833059941418469 | 0.0006365649751387537 |
| `observations[bad-038].areas[1].seconds` | 2.0720078269951046 | 2.0817385999835096 |
| `observations[bad-038].judge_seconds` | 2.1343965400010347 | 2.1541037379647605 |
| `observations[bad-039].areas[1].seconds` | 2.1050513270311058 | 2.1035026449826546 |
| `observations[bad-039].judge_seconds` | 2.1700422260328196 | 2.1676862699678168 |
| `observations[bad-040].areas[1].seconds` | 2.278595866053365 | 2.288971336965915 |
| `observations[bad-040].judge_seconds` | 2.628378368972335 | 2.640093184018042 |
| `observations[bad-041].areas[1].seconds` | 2.9840716260368936 | 2.973880284000188 |
| `observations[bad-041].judge_seconds` | 3.2586712379707024 | 3.2503057009889744 |
| `observations[bad-042].areas[1].seconds` | 2.127748769009486 | 2.109385374991689 |
| `observations[bad-042].judge_seconds` | 2.2385951149626635 | 2.220404981984757 |
| `observations[bad-043].areas[1].seconds` | 2.9254563110298477 | 2.9442917450214736 |
| `observations[bad-043].judge_seconds` | 3.379667447996326 | 3.4007953419932164 |
| `observations[bad-044].areas[1].seconds` | 2.331541082006879 | 2.3278137909946963 |
| `observations[bad-044].judge_seconds` | 2.5216681759920903 | 2.516835800022818 |
| `observations[bad-045].areas[1].seconds` | 2.326262383023277 | 2.326151133980602 |
| `observations[bad-045].judge_seconds` | 2.512815285997931 | 2.5134555239928886 |
| `observations[bad-046].areas[1].seconds` | 2.172588752990123 | 2.1603201759862714 |
| `observations[bad-046].judge_seconds` | 2.416763656947296 | 2.4082433379953727 |
| `observations[bad-047].areas[1].seconds` | 2.0842346159624867 | 2.0908463470404968 |
| `observations[bad-047].judge_seconds` | 2.1410810200031847 | 2.1504188789986074 |
| `observations[bad-048].judge_seconds` | 0.0006241879891604185 | 0.0006362529820762575 |
| `observations[bad-049].areas[1].seconds` | 2.8036125209764577 | 2.813877019973006 |
| `observations[bad-049].judge_seconds` | 2.9396350090391934 | 2.953631508979015 |
| `observations[bad-050].areas[1].seconds` | 2.067168573033996 | 2.0709602650022134 |
| `observations[bad-050].judge_seconds` | 2.3010645199683495 | 2.3054185420041904 |
| `observations[bad-051].areas[1].seconds` | 2.226897934975568 | 2.223954859015066 |
| `observations[bad-051].judge_seconds` | 2.3174963620258495 | 2.31508055300219 |
| `observations[bad-052].areas[1].seconds` | 2.2437070040032268 | 2.242192644975148 |
| `observations[bad-052].judge_seconds` | 2.3136874109623022 | 2.3162199209909886 |
| `observations[bad-053].areas[1].seconds` | 2.26142597803846 | 2.2755561029771343 |
| `observations[bad-053].judge_seconds` | 2.4090173419681378 | 2.4251772059942596 |
| `observations[bad-054].areas[1].seconds` | 2.5459768250002526 | 2.5568919790093787 |
| `observations[bad-054].judge_seconds` | 2.737108460976742 | 2.748953005997464 |
| `observations[bad-055].areas[1].seconds` | 2.120322306989692 | 2.1096343270037323 |
| `observations[bad-055].judge_seconds` | 2.300191532005556 | 2.290514043997973 |
| `observations[bad-056].areas[1].seconds` | 2.131957994948607 | 2.1178496269858442 |
| `observations[bad-056].judge_seconds` | 2.3081368249841034 | 2.29760279704351 |
| `observations[bad-057].areas[1].seconds` | 2.0648798319743946 | 2.051879098988138 |
| `observations[bad-057].judge_seconds` | 2.1179075120016932 | 2.104781746980734 |
| `observations[bad-058].areas[1].seconds` | 2.095056038000621 | 2.086375863989815 |
| `observations[bad-058].judge_seconds` | 2.14248423097888 | 2.133814960019663 |
| `observations[bad-059].areas[1].seconds` | 2.07539535604883 | 2.0819150680326857 |
| `observations[bad-059].judge_seconds` | 2.2955862440285273 | 2.308246234024409 |
| `observations[bad-060].judge_seconds` | 0.0006288069998845458 | 0.0006891689845360816 |
| `observations[bad-061].areas[1].seconds` | 2.0713251150446013 | 2.0561062279739417 |
| `observations[bad-061].judge_seconds` | 2.1176668129628524 | 2.102720279013738 |
| `observations[bad-062].areas[1].seconds` | 2.0926463609794155 | 2.082105125999078 |
| `observations[bad-062].judge_seconds` | 2.1419268010067753 | 2.1320325050037354 |
| `observations[bad-063].areas[1].seconds` | 2.062528639973607 | 2.0531147749861702 |
| `observations[bad-063].judge_seconds` | 2.1109331870102324 | 2.103264687990304 |
| `observations[bad-064].areas[1].seconds` | 2.181939519010484 | 2.1762841810123064 |
| `observations[bad-064].judge_seconds` | 2.2310077670263126 | 2.22545488801552 |
| `observations[bad-065].areas[1].seconds` | 2.117558939033188 | 2.099893581995275 |
| `observations[bad-065].judge_seconds` | 2.184387287008576 | 2.1677249069907703 |
| `observations[bad-066].areas[1].seconds` | 2.362227106001228 | 2.350786248978693 |
| `observations[bad-066].judge_seconds` | 2.414528216002509 | 2.4036723310127854 |
| `observations[bad-067].areas[1].seconds` | 1.9781650000368245 | 1.9661383049678989 |
| `observations[bad-067].judge_seconds` | 2.0257543210173026 | 2.013514405989554 |
| `observations[bad-068].areas[1].seconds` | 2.247663179994561 | 2.2435728380223736 |
| `observations[bad-068].judge_seconds` | 2.344506392022595 | 2.342440499982331 |
| `observations[bad-069].areas[1].seconds` | 2.041478630970232 | 2.026628131978214 |
| `observations[bad-069].judge_seconds` | 2.093937936006114 | 2.078409145004116 |
| `observations[bad-070].areas[1].seconds` | 2.0419608739903197 | 2.0200033159926534 |
| `observations[bad-070].judge_seconds` | 2.112081662984565 | 2.0900134150288068 |
| `observations[bad-071].areas[1].seconds` | 2.143589632003568 | 2.131695600983221 |
| `observations[bad-071].judge_seconds` | 2.2136385510093533 | 2.2029470470151864 |
| `observations[bad-072].areas[1].seconds` | 2.1330681379768066 | 2.1142736120382324 |
| `observations[bad-072].judge_seconds` | 2.1969681580085307 | 2.1791439169901423 |
| `observations[bad-073].areas[1].seconds` | 2.3496738679823466 | 2.3331597319920547 |
| `observations[bad-073].judge_seconds` | 2.399157982028555 | 2.382080482027959 |
| `observations[bad-074].areas[1].seconds` | 2.061025118047837 | 2.0622464070329443 |
| `observations[bad-074].judge_seconds` | 2.112058020022232 | 2.111037808994297 |
| `observations[bad-075].areas[1].seconds` | 2.0995131679810584 | 2.0971779670217074 |
| `observations[bad-075].judge_seconds` | 2.146412438014522 | 2.144194055988919 |
| `observations[bad-076].judge_seconds` | 0.00141872902167961 | 0.0006978690507821739 |
| `observations[bad-077].areas[1].seconds` | 2.0353053170256317 | 2.043774008983746 |
| `observations[bad-077].judge_seconds` | 2.0852928449749015 | 2.0956035749986768 |
| `observations[bad-078].areas[1].seconds` | 1.9787747989757918 | 1.9765810569515452 |
| `observations[bad-078].judge_seconds` | 2.023199333983939 | 2.0257610349799506 |
| `observations[bad-079].areas[1].seconds` | 2.06877276400337 | 2.0574130410095677 |
| `observations[bad-079].judge_seconds` | 2.1157198929577135 | 2.104479514993727 |
| `observations[bad-080].areas[1].seconds` | 2.4696862929849885 | 2.464772477047518 |
| `observations[bad-080].judge_seconds` | 2.534625649044756 | 2.5298081890214235 |
| `observations[bad-081].areas[1].seconds` | 1.8844578780117445 | 1.8763840040192008 |
| `observations[bad-081].judge_seconds` | 1.9339486740063876 | 1.9247820370364934 |
| `observations[bad-082].areas[1].seconds` | 2.3636861449922435 | 2.370768274005968 |
| `observations[bad-082].judge_seconds` | 2.4165083969710395 | 2.421464245999232 |
| `observations[bad-083].areas[1].seconds` | 2.11063967802329 | 2.100858015997801 |
| `observations[bad-083].judge_seconds` | 2.1623553590034135 | 2.151750040007755 |
| `observations[bad-084].areas[1].seconds` | 2.2241035139886662 | 2.2203480810276233 |
| `observations[bad-084].judge_seconds` | 2.3066944429883733 | 2.301745333010331 |
| `observations[bad-085].areas[1].seconds` | 2.099365728034172 | 2.0945227929623798 |
| `observations[bad-085].judge_seconds` | 2.144510963000357 | 2.139328324003145 |
| `observations[bad-086].areas[1].seconds` | 1.9729544089641422 | 1.9729362110374495 |
| `observations[bad-086].judge_seconds` | 2.0237222139840014 | 2.023782379052136 |
| `observations[bad-087].areas[1].seconds` | 2.4119189259945415 | 2.3960617010015994 |
| `observations[bad-087].judge_seconds` | 2.4622853270266205 | 2.4432648790534586 |
| `observations[bad-088].areas[1].seconds` | 2.2152352620032616 | 2.212569158000406 |
| `observations[bad-088].judge_seconds` | 2.2648684429586865 | 2.2614647740265355 |
| `observations[bad-089].areas[1].seconds` | 2.381921833031811 | 2.3712116320384666 |
| `observations[bad-089].judge_seconds` | 2.439554161974229 | 2.427997004997451 |
| `observations[bad-090].areas[1].seconds` | 2.69567637599539 | 2.6891950459685177 |
| `observations[bad-090].judge_seconds` | 2.7507731840014458 | 2.74492668005405 |
| `observations[bad-091].areas[1].seconds` | 1.9696539799915627 | 1.9688265990116633 |
| `observations[bad-091].judge_seconds` | 2.0200810890528373 | 2.0152104169828817 |
| `observations[bad-092].areas[1].seconds` | 2.283153210999444 | 2.2748124030185863 |
| `observations[bad-092].judge_seconds` | 2.3574035790516064 | 2.3500663510058075 |
| `observations[bad-093].areas[1].seconds` | 2.5739264019648544 | 2.5587046789587475 |
| `observations[bad-093].judge_seconds` | 2.6400101019535214 | 2.6273652560194023 |
| `observations[bad-094].areas[1].seconds` | 2.3979123780154623 | 2.3785606830497272 |
| `observations[bad-094].judge_seconds` | 2.4473932670080103 | 2.4289146320079453 |
| `observations[bad-095].areas[1].seconds` | 1.9426587789785117 | 1.9381270019803196 |
| `observations[bad-095].judge_seconds` | 1.9926273230230436 | 1.9839049889706075 |
| `observations[bad-096].judge_seconds` | 0.0006042689783498645 | 0.0006629839772358537 |
| `observations[bad-097].areas[1].seconds` | 2.214633085997775 | 2.214345894055441 |
| `observations[bad-097].judge_seconds` | 2.2631107780034654 | 2.258048254996538 |
| `observations[bad-098].areas[1].seconds` | 2.224298768036533 | 2.214895006036386 |
| `observations[bad-098].judge_seconds` | 2.2724319780245423 | 2.2607734089833684 |
| `observations[bad-099].areas[1].seconds` | 2.2541099990485236 | 2.249005847959779 |
| `observations[bad-099].judge_seconds` | 2.322323234984651 | 2.3093375579919666 |
| `observations[good-0011].judge_seconds` | 0.0005967820179648697 | 0.0006112140254117548 |
| `observations[good-0013].judge_seconds` | 0.00048488902393728495 | 0.0005167610361240804 |
| `observations[good-0016].judge_seconds` | 0.0005066610174253583 | 0.0004832590348087251 |
| `observations[good-0024].judge_seconds` | 0.00040689395973458886 | 0.00042395200580358505 |
| `observations[good-0026].judge_seconds` | 0.0004900550120510161 | 0.0004940740182064474 |
| `observations[good-0027].judge_seconds` | 0.0006523480406031013 | 0.0006618230254389346 |
| `observations[good-0046].judge_seconds` | 0.00044700998114421964 | 0.00042555801337584853 |
| `observations[good-0100].judge_seconds` | 0.0005029599997214973 | 0.0005135950050316751 |
| `observations[good-0107].judge_seconds` | 0.0031835000263527036 | 0.0032398850307799876 |
| `observations[good-0159].judge_seconds` | 0.0004497790359891951 | 0.00044678401900455356 |
| `observations[good-0168].judge_seconds` | 0.0004991809837520123 | 0.0004852740094065666 |
| `observations[good-0170].judge_seconds` | 0.00020221300655975938 | 0.0003656329936347902 |
| `observations[good-0172].judge_seconds` | 0.0004022539942525327 | 0.00040604203240945935 |
| `observations[good-0174].areas[1].seconds` | 2.0209701330168173 | 2.0387384470086545 |
| `observations[good-0174].judge_seconds` | 2.0653931950218976 | 2.0910084000206552 |
| `observations[good-0178].judge_seconds` | 0.00037639198126271367 | 0.00028709997422993183 |
| `observations[good-0187].judge_seconds` | 0.0004232969949953258 | 0.00042851397302001715 |
| `observations[good-0196].judge_seconds` | 0.0004361890023574233 | 0.00047755101695656776 |
| `observations[good-0208].judge_seconds` | 0.0005802279920317233 | 0.000586897018365562 |
| `observations[good-0214].areas[1].seconds` | 1.9050700480001979 | 1.9070424070232548 |
| `observations[good-0214].judge_seconds` | 1.95616052596597 | 1.957457743003033 |
| `observations[good-0215].judge_seconds` | 0.000488924968522042 | 0.0004866859526373446 |
| `observations[good-0237].judge_seconds` | 0.00045880896504968405 | 0.0004437989555299282 |
| `observations[good-0261].areas[1].seconds` | 1.9515896609518677 | 1.9699838529923 |
| `observations[good-0261].judge_seconds` | 1.9993349729920737 | 2.0222371929557994 |
| `observations[good-0286].judge_seconds` | 0.0004651580238714814 | 0.0004829589743167162 |
| `observations[good-0294].judge_seconds` | 0.0006226919940672815 | 0.0006325019639916718 |
| `observations[good-0297].judge_seconds` | 0.0004474290180951357 | 0.0004265200113877654 |
| `observations[good-0303].judge_seconds` | 0.00045518798287957907 | 0.00047185004223138094 |
| `observations[good-0306].areas[1].seconds` | 2.0526208539959043 | 2.0587785379611887 |
| `observations[good-0306].judge_seconds` | 2.0993889049859717 | 2.106930984009523 |
| `observations[good-0320].judge_seconds` | 0.00019041099585592747 | 0.00011381000513210893 |
| `observations[good-0333].areas[1].seconds` | 1.8669568679761142 | 1.881495014007669 |
| `observations[good-0333].judge_seconds` | 1.911475439032074 | 1.9254417959600687 |
| `observations[good-0363].judge_seconds` | 0.00041471398435533047 | 0.00044684403110295534 |
| `observations[good-0377].judge_seconds` | 0.0004635479999706149 | 0.0004546280251815915 |
| `observations[good-0394].judge_seconds` | 0.0004148070001974702 | 0.0004244419978931546 |
| `observations[good-0400].judge_seconds` | 0.0001994660124182701 | 0.0003571119741536677 |
| `observations[good-0402].judge_seconds` | 0.0005049259634688497 | 0.0004791649989783764 |
| `observations[good-0417].judge_seconds` | 0.0001951369922608137 | 0.00011652900138869882 |
| `observations[good-0423].judge_seconds` | 0.0001960800145752728 | 0.0001087019918486476 |
| `observations[good-0427].judge_seconds` | 0.0006333990022540092 | 0.0006429080385714769 |
| `observations[good-0457].judge_seconds` | 0.0004357710131444037 | 0.0004677909892052412 |
| `observations[good-0469].judge_seconds` | 0.00019560998771339655 | 0.00036607799120247364 |
| `observations[good-0479].judge_seconds` | 0.0006140410550870001 | 0.0006310580065473914 |
| `observations[good-0483].judge_seconds` | 0.00038360897451639175 | 0.0003657859633676708 |
| `observations[good-0484].judge_seconds` | 0.0005366000114008784 | 0.0005831780144944787 |
| `observations[good-0488].judge_seconds` | 0.0004035480087623 | 0.00043162499787285924 |
| `observations[good-0490].judge_seconds` | 0.0006422239821404219 | 0.0006266880081966519 |
| `observations[good-0514].judge_seconds` | 0.0004198250244371593 | 0.0004225579905323684 |
| `observations[good-0518].areas[1].seconds` | 1.9641580439638346 | 1.9672677440103143 |
| `observations[good-0518].judge_seconds` | 2.0107426440226845 | 2.0164721900364384 |
| `observations[good-0520].judge_seconds` | 0.00040863698814064264 | 0.0004470730200409889 |
| `observations[good-0525].judge_seconds` | 0.0001911289873532951 | 0.0003638380439952016 |
| `observations[good-0545].judge_seconds` | 0.0003734820056706667 | 0.00038351299008354545 |
| `observations[good-0552].judge_seconds` | 0.0004963219980709255 | 0.0004968349821865559 |
| `observations[good-0569].judge_seconds` | 0.0004752480308525264 | 0.0004792649997398257 |
| `observations[good-0615].judge_seconds` | 0.0003728829906322062 | 0.0003780089900828898 |
| `observations[good-0617].judge_seconds` | 0.00045355799375101924 | 0.00043534900760278106 |
| `observations[good-0619].judge_seconds` | 0.00042536796536296606 | 0.0004885789821855724 |
| `observations[good-0621].areas[1].seconds` | 1.9893405560287647 | 2.007645303965546 |
| `observations[good-0621].judge_seconds` | 2.0347521489602514 | 2.054424962028861 |
| `observations[good-0629].judge_seconds` | 0.00044092501047998667 | 0.00041470699943602085 |
| `observations[good-0631].judge_seconds` | 0.00019554502796381712 | 0.0003753129858523607 |
| `observations[good-0648].judge_seconds` | 0.0006187910330481827 | 0.0006153880385681987 |
| `observations[good-0654].judge_seconds` | 0.0002732189605012536 | 0.0003949279780499637 |
| `observations[good-0657].judge_seconds` | 0.0004945200053043664 | 0.00047951500164344907 |
| `observations[good-0659].judge_seconds` | 0.0004297869745641947 | 0.0004448099643923342 |
| `observations[good-0674].areas[1].seconds` | 2.411804861971177 | 2.419715786993038 |
| `observations[good-0674].judge_seconds` | 2.4582697490113787 | 2.47136937599862 |
| `observations[good-0684].areas[1].seconds` | 2.048536968010012 | 2.062306453997735 |
| `observations[good-0684].judge_seconds` | 2.094336974027101 | 2.1083563229767606 |
| `observations[good-0685].judge_seconds` | 0.00020387000404298306 | 0.00029179698321968317 |
| `observations[good-0688].judge_seconds` | 0.00039381900569424033 | 0.0004156489740125835 |
| `observations[good-0690].judge_seconds` | 0.0004672359791584313 | 0.00048226903891190886 |
| `observations[good-0694].areas[1].seconds` | 2.1935900290263817 | 2.2050000480376184 |
| `observations[good-0694].judge_seconds` | 2.2540268630255014 | 2.265201926988084 |
| `observations[good-0705].areas[1].seconds` | 1.9574176779715344 | 1.9714532430516556 |
| `observations[good-0705].judge_seconds` | 2.000661758997012 | 2.0174191810074262 |
| `observations[good-0725].judge_seconds` | 0.0004365680506452918 | 0.00040539802284911275 |
| `observations[good-0730].areas[1].seconds` | 2.122131074022036 | 2.135796047979966 |
| `observations[good-0730].judge_seconds` | 2.242757399973925 | 2.25247883197153 |
| `observations[good-0735].judge_seconds` | 0.0003849370405077934 | 0.0003930180100724101 |
| `observations[good-0739].judge_seconds` | 0.0006024329923093319 | 0.0006475130212493241 |
| `observations[good-0751].areas[1].seconds` | 2.2205007250304334 | 2.232325730030425 |
| `observations[good-0751].judge_seconds` | 2.258994266972877 | 2.2699987220112234 |
| `observations[good-0755].judge_seconds` | 0.0006090120295993984 | 0.0006591569981537759 |
| `observations[good-0764].areas[1].seconds` | 2.2252179619972594 | 2.2346042749704793 |
| `observations[good-0764].judge_seconds` | 2.2719317720038816 | 2.282044147956185 |
| `observations[good-0768].judge_seconds` | 0.000420914962887764 | 0.00042277900502085686 |
| `observations[good-0779].judge_seconds` | 0.000424800964538008 | 0.0005168660427443683 |
| `observations[good-0784].judge_seconds` | 0.0006079559680074453 | 0.0006645750254392624 |
| `observations[good-0796].judge_seconds` | 0.0003848570049740374 | 0.0003986089723184705 |
| `observations[good-0797].areas[1].seconds` | 2.165440213982947 | 2.1802109090494923 |
| `observations[good-0797].judge_seconds` | 2.2067440020036884 | 2.2204047570121475 |
| `observations[good-0800].judge_seconds` | 0.0004418499884195626 | 0.0005085000302642584 |
| `observations[good-0804].judge_seconds` | 0.0004556899657472968 | 0.00043714995263144374 |
| `observations[good-0811].judge_seconds` | 0.00011192902456969023 | 0.0004674589727073908 |
| `observations[good-0844].judge_seconds` | 0.00043501402251422405 | 0.0004397500306367874 |
| `observations[good-0869].judge_seconds` | 0.00020575395319610834 | 0.00011264695785939693 |
| `observations[good-0871].judge_seconds` | 0.00011096498928964138 | 0.0004192169872112572 |
| `observations[good-0892].judge_seconds` | 0.0004279929562471807 | 0.0004459829651750624 |
| `observations[good-0900].judge_seconds` | 0.0006011970108374953 | 0.0005970080383121967 |
| `observations[good-0920].areas[1].seconds` | 2.29089548997581 | 2.3113481089822017 |
| `observations[good-0920].judge_seconds` | 2.3774526169872843 | 2.3980320749687962 |
| `observations[good-0923].areas[1].seconds` | 1.951187041006051 | 1.9742109409999102 |
| `observations[good-0923].judge_seconds` | 1.9945984759833664 | 2.0181234540068544 |
| `observations[good-0935].judge_seconds` | 0.0004962999955751002 | 0.000504697032738477 |
| `observations[good-0940].judge_seconds` | 0.0006068919901736081 | 0.0006068830261938274 |
| `observations[good-0952].judge_seconds` | 0.0002529590274207294 | 0.0004197800299152732 |
| `observations[good-0957].areas[1].seconds` | 2.132372999971267 | 2.1426534929778427 |
| `observations[good-0957].judge_seconds` | 2.176190770987887 | 2.185951514984481 |
| `observations[good-0964].judge_seconds` | 0.00042033405043184757 | 0.00045476399827748537 |
| `observations[good-0971].judge_seconds` | 0.0006111430120654404 | 0.0005958469700999558 |
| `observations[good-0974].areas[1].seconds` | 1.865826205990743 | 1.882190667965915 |
| `observations[good-0974].judge_seconds` | 1.9053613599971868 | 1.9217227440094575 |
| `observations[good-0989].judge_seconds` | 0.0006395770469680429 | 0.0005960179842077196 |
| `observations[good-0994].judge_seconds` | 0.0003883769968524575 | 0.0004395750002004206 |
| `observations[good-1000].judge_seconds` | 0.00038620299892500043 | 0.00038380298065021634 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `observations[bad-000].areas[1].seconds` | 2.2236145900096744 | 2.217237772012595 |
| `observations[bad-000].judge_seconds` | 2.299463456030935 | 2.3008338469662704 |
| `observations[bad-001].areas[1].seconds` | 2.065854193002451 | 2.069945918978192 |
| `observations[bad-001].judge_seconds` | 2.119253718992695 | 2.1266551710432395 |
| `observations[bad-002].areas[1].seconds` | 2.1404294859967194 | 2.113949451013468 |
| `observations[bad-002].judge_seconds` | 2.4079023029771633 | 2.376626074023079 |
| `observations[bad-003].areas[1].seconds` | 2.2371194410370663 | 2.2401101359864697 |
| `observations[bad-003].judge_seconds` | 2.306381670990959 | 2.3077124640112743 |
| `observations[bad-004].areas[1].seconds` | 2.1157374759786762 | 2.1204952290281653 |
| `observations[bad-004].judge_seconds` | 2.189408086007461 | 2.1955291390186176 |
| `observations[bad-005].areas[1].seconds` | 1.9397805850021541 | 1.9459683500463143 |
| `observations[bad-005].judge_seconds` | 1.989598255022429 | 1.9986499350052327 |
| `observations[bad-006].areas[1].seconds` | 2.092575688031502 | 2.0871409159735776 |
| `observations[bad-006].judge_seconds` | 2.2017520120134577 | 2.1927976639708504 |
| `observations[bad-007].areas[1].seconds` | 1.9838600269868039 | 1.9846432119957171 |
| `observations[bad-007].judge_seconds` | 2.0329025500104763 | 2.0336806250270456 |
| `observations[bad-008].areas[1].seconds` | 2.0393010190455243 | 2.0476662699948065 |
| `observations[bad-008].judge_seconds` | 2.088170093949884 | 2.0967459130333737 |
| `observations[bad-009].areas[1].seconds` | 2.037488850997761 | 2.037560858996585 |
| `observations[bad-009].judge_seconds` | 2.0878724830108695 | 2.087639174016658 |
| `observations[bad-010].areas[1].seconds` | 2.1102611790411174 | 2.111513757961802 |
| `observations[bad-010].judge_seconds` | 2.23495815199567 | 2.235136783972848 |
| `observations[bad-011].areas[1].seconds` | 2.1925288920174353 | 2.1923299779882655 |
| `observations[bad-011].judge_seconds` | 2.2833946949685924 | 2.284526908013504 |
| `observations[bad-012].areas[1].seconds` | 2.159451935964171 | 2.1623820060049184 |
| `observations[bad-012].judge_seconds` | 2.2548749150009826 | 2.263499705004506 |
| `observations[bad-013].areas[1].seconds` | 2.094847492990084 | 2.0872913890052587 |
| `observations[bad-013].judge_seconds` | 2.181598850991577 | 2.1734233510214835 |
| `observations[bad-014].areas[1].seconds` | 2.2357758230064064 | 2.2206408649799414 |
| `observations[bad-014].judge_seconds` | 2.3089069749694318 | 2.2940422859974205 |
| `observations[bad-015].areas[1].seconds` | 2.071243434038479 | 2.0671971780247986 |
| `observations[bad-015].judge_seconds` | 2.1604075109935366 | 2.155994087981526 |
| `observations[bad-016].areas[1].seconds` | 2.1011122920317575 | 2.104460307979025 |
| `observations[bad-016].judge_seconds` | 2.167703806015197 | 2.1712095289840363 |
| `observations[bad-017].areas[1].seconds` | 2.2707079430110753 | 2.284029479022138 |
| `observations[bad-017].judge_seconds` | 2.4326415049727075 | 2.4494864009902813 |
| `observations[bad-018].areas[1].seconds` | 2.1036723389988765 | 2.11117321299389 |
| `observations[bad-018].judge_seconds` | 2.166229508991819 | 2.175435452023521 |
| `observations[bad-019].areas[1].seconds` | 2.2384213199838996 | 2.2442268659942783 |
| `observations[bad-019].judge_seconds` | 2.3341420509968884 | 2.339383671991527 |
| `observations[bad-020].areas[1].seconds` | 2.345047626993619 | 2.350837313977536 |
| `observations[bad-020].judge_seconds` | 2.3945132779772393 | 2.4001104600029066 |
| `observations[bad-021].areas[1].seconds` | 2.2828791909851134 | 2.283844918012619 |
| `observations[bad-021].judge_seconds` | 2.4034693589783274 | 2.404001421004068 |
| `observations[bad-022].areas[1].seconds` | 2.035174454038497 | 2.041902701021172 |
| `observations[bad-022].judge_seconds` | 2.092491867020726 | 2.099011764046736 |
| `observations[bad-023].areas[1].seconds` | 1.9821299589821137 | 1.9915324879693799 |
| `observations[bad-023].judge_seconds` | 2.0501171849900857 | 2.059534592961427 |
| `observations[bad-024].areas[1].seconds` | 2.1106431009829976 | 2.1077032270259224 |
| `observations[bad-024].judge_seconds` | 2.226778039999772 | 2.22299166303128 |
| `observations[bad-025].areas[1].seconds` | 2.2367926060105674 | 2.2437631909851916 |
| `observations[bad-025].judge_seconds` | 2.3083606169675477 | 2.314898179960437 |
| `observations[bad-026].areas[1].seconds` | 2.015111303946469 | 2.0107497010030784 |
| `observations[bad-026].judge_seconds` | 2.0898349030176178 | 2.0851658969768323 |
| `observations[bad-027].areas[1].seconds` | 2.227338675002102 | 2.237191708001774 |
| `observations[bad-027].judge_seconds` | 2.3259657000307925 | 2.3343064959626645 |
| `observations[bad-028].areas[1].seconds` | 2.106959696044214 | 2.1163788510020822 |
| `observations[bad-028].judge_seconds` | 2.1788977720425464 | 2.1865239319740795 |
| `observations[bad-029].areas[1].seconds` | 2.277712181035895 | 2.2766457030083984 |
| `observations[bad-029].judge_seconds` | 2.357661633985117 | 2.3558522980310954 |
| `observations[bad-030].areas[1].seconds` | 2.006526774028316 | 2.0205205630045384 |
| `observations[bad-030].judge_seconds` | 2.076685855980031 | 2.0858640120131895 |
| `observations[bad-031].areas[1].seconds` | 2.0952741610235535 | 2.100788604991976 |
| `observations[bad-031].judge_seconds` | 2.19118389103096 | 2.196858677023556 |
| `observations[bad-032].areas[1].seconds` | 2.225297095021233 | 2.2268107169657014 |
| `observations[bad-032].judge_seconds` | 2.3061093849828467 | 2.3083680240088142 |
| `observations[bad-033].areas[1].seconds` | 2.2269034900236875 | 2.2354018320329487 |
| `observations[bad-033].judge_seconds` | 2.319517489988357 | 2.328594953985885 |
| `observations[bad-034].areas[1].seconds` | 2.26361593301408 | 2.270983719965443 |
| `observations[bad-034].judge_seconds` | 2.401002300030086 | 2.40763876499841 |
| `observations[bad-035].areas[1].seconds` | 2.0436021449859254 | 2.0535185059998184 |
| `observations[bad-035].judge_seconds` | 2.1311911029624753 | 2.141480451973621 |
| `observations[bad-036].areas[1].seconds` | 2.2586138889892027 | 2.2729832520126365 |
| `observations[bad-036].judge_seconds` | 2.368721370003186 | 2.3828210050123744 |
| `observations[bad-037].areas[1].seconds` | 2.291320669988636 | 2.293988385994453 |
| `observations[bad-037].judge_seconds` | 2.3903459389694035 | 2.3920191130018793 |
| `observations[bad-038].areas[1].seconds` | 2.002283034962602 | 2.0119673630106263 |
| `observations[bad-038].judge_seconds` | 2.0522115269559436 | 2.0603432330535725 |
| `observations[bad-039].areas[1].seconds` | 2.082619113032706 | 2.0846406610216945 |
| `observations[bad-039].judge_seconds` | 2.197065852000378 | 2.19765147799626 |
| `observations[bad-040].areas[1].seconds` | 2.1033707799506374 | 2.1059166089980863 |
| `observations[bad-040].judge_seconds` | 2.283986207039561 | 2.2831529550021514 |
| `observations[bad-041].areas[1].seconds` | 2.3840887579717673 | 2.4004033009987324 |
| `observations[bad-041].judge_seconds` | 2.479271775984671 | 2.4951753779896535 |
| `observations[bad-042].areas[1].seconds` | 2.177657697000541 | 2.19437703298172 |
| `observations[bad-042].judge_seconds` | 2.236951476021204 | 2.2538220189744607 |
| `observations[bad-043].areas[1].seconds` | 2.201191025960725 | 2.205938700994011 |
| `observations[bad-043].judge_seconds` | 2.305170862993691 | 2.310303381003905 |
| `observations[bad-044].areas[1].seconds` | 2.2569275139831007 | 2.287742404965684 |
| `observations[bad-044].judge_seconds` | 2.3303729980252683 | 2.363020766992122 |
| `observations[bad-045].areas[1].seconds` | 2.1362161510041915 | 2.1441452690050937 |
| `observations[bad-045].judge_seconds` | 2.3792644079658203 | 2.394870225980412 |
| `observations[bad-046].judge_seconds` | 0.0006644579698331654 | 0.00067310401936993 |
| `observations[bad-047].areas[1].seconds` | 2.1590267500141636 | 2.166492116986774 |
| `observations[bad-047].judge_seconds` | 2.205176351009868 | 2.212838245963212 |
| `observations[bad-048].areas[1].seconds` | 2.1524393259896897 | 2.162383634946309 |
| `observations[bad-048].judge_seconds` | 2.2019343900028616 | 2.212076321011409 |
| `observations[bad-049].areas[1].seconds` | 2.1396594480029307 | 2.1502080489881337 |
| `observations[bad-049].judge_seconds` | 2.397638130991254 | 2.411243889015168 |
| `observations[bad-050].areas[1].seconds` | 2.2702777740196325 | 2.2844701079884544 |
| `observations[bad-050].judge_seconds` | 2.3267175710061565 | 2.3386822939501144 |
| `observations[bad-051].areas[1].seconds` | 2.037426639988553 | 2.049083171004895 |
| `observations[bad-051].judge_seconds` | 2.0881687339860946 | 2.101263978984207 |
| `observations[bad-052].areas[1].seconds` | 2.133914284000639 | 2.142094781040214 |
| `observations[bad-052].judge_seconds` | 2.364721877966076 | 2.373403823992703 |
| `observations[bad-053].areas[1].seconds` | 2.0947789259953424 | 2.109208541980479 |
| `observations[bad-053].judge_seconds` | 2.3449491770006716 | 2.357642079994548 |
| `observations[bad-054].areas[1].seconds` | 2.1660887069883756 | 2.172690985025838 |
| `observations[bad-054].judge_seconds` | 2.2090521790087223 | 2.22516676801024 |
| `observations[bad-055].areas[1].seconds` | 2.2186329509713687 | 2.229559858038556 |
| `observations[bad-055].judge_seconds` | 2.2656972410040908 | 2.2782354810042307 |
| `observations[bad-056].areas[1].seconds` | 2.2417981839971617 | 2.254877685045358 |
| `observations[bad-056].judge_seconds` | 2.3023635760182515 | 2.31467207998503 |
| `observations[bad-057].areas[1].seconds` | 2.1163267040392384 | 2.1289736280450597 |
| `observations[bad-057].judge_seconds` | 2.3734850860200822 | 2.387833787011914 |
| `observations[bad-058].areas[1].seconds` | 2.0772079559974372 | 2.0766630209982395 |
| `observations[bad-058].judge_seconds` | 2.127804022980854 | 2.1216291419696063 |
| `observations[bad-059].areas[1].seconds` | 2.070563137996942 | 2.0677627340191975 |
| `observations[bad-059].judge_seconds` | 2.1222655570018105 | 2.1138148460304365 |
| `observations[bad-060].areas[1].seconds` | 2.2148392110248096 | 2.2114294369821437 |
| `observations[bad-060].judge_seconds` | 2.284399427997414 | 2.278628200991079 |
| `observations[bad-061].areas[1].seconds` | 2.0529807110433467 | 2.043139539018739 |
| `observations[bad-061].judge_seconds` | 2.10200012504356 | 2.087584416032769 |
| `observations[bad-062].areas[1].seconds` | 2.1093404599814676 | 2.097646126989275 |
| `observations[bad-062].judge_seconds` | 2.342492625990417 | 2.328581759997178 |
| `observations[bad-063].areas[1].seconds` | 1.972826627024915 | 1.9599594000028446 |
| `observations[bad-063].judge_seconds` | 2.030807956994977 | 2.014703209977597 |
| `observations[bad-064].areas[1].seconds` | 2.085553632990923 | 2.0793980240123346 |
| `observations[bad-064].judge_seconds` | 2.1377515479689464 | 2.1304919460089877 |
| `observations[bad-065].areas[1].seconds` | 2.1278524920344353 | 2.130421629000921 |
| `observations[bad-065].judge_seconds` | 2.430490929982625 | 2.433574690017849 |
| `observations[bad-066].areas[1].seconds` | 2.273211999970954 | 2.269981697027106 |
| `observations[bad-066].judge_seconds` | 2.3328753110254183 | 2.3257513199932873 |
| `observations[bad-067].areas[1].seconds` | 2.0513288420042954 | 2.037750846997369 |
| `observations[bad-067].judge_seconds` | 2.100600369973108 | 2.0847646290203556 |
| `observations[bad-068].areas[1].seconds` | 2.1179820459801704 | 2.121236831007991 |
| `observations[bad-068].judge_seconds` | 2.4361849460401572 | 2.439190042030532 |
| `observations[bad-069].areas[1].seconds` | 2.0797225179849193 | 2.084069046017248 |
| `observations[bad-069].judge_seconds` | 2.1332180140307173 | 2.13551577803446 |
| `observations[bad-070].areas[1].seconds` | 2.0619026450440288 | 2.058117049979046 |
| `observations[bad-070].judge_seconds` | 2.111604587000329 | 2.106175846012775 |
| `observations[bad-071].areas[1].seconds` | 2.067210312001407 | 2.06955812999513 |
| `observations[bad-071].judge_seconds` | 2.1233577330131084 | 2.1203109390335158 |
| `observations[bad-072].judge_seconds` | 0.0006466570193879306 | 0.0006753579946234822 |
| `observations[bad-073].areas[1].seconds` | 2.1355760599835776 | 2.136426425015088 |
| `observations[bad-073].judge_seconds` | 2.4033062170492485 | 2.392545736976899 |
| `observations[bad-074].areas[1].seconds` | 2.1042502020136453 | 2.0998379689990543 |
| `observations[bad-074].judge_seconds` | 2.1533639900153503 | 2.14746752200881 |
| `observations[bad-075].areas[1].seconds` | 2.085522051958833 | 2.0818512280238792 |
| `observations[bad-075].judge_seconds` | 2.2186685090418905 | 2.2061951430514455 |
| `observations[bad-076].areas[1].seconds` | 2.15238537004916 | 2.164841787016485 |
| `observations[bad-076].judge_seconds` | 2.2413644500193186 | 2.252758755988907 |
| `observations[bad-077].areas[1].seconds` | 1.973511687014252 | 1.9739919420098886 |
| `observations[bad-077].judge_seconds` | 2.038749839994125 | 2.035868392966222 |
| `observations[bad-078].areas[1].seconds` | 1.9862745169666596 | 2.0130038170027547 |
| `observations[bad-078].judge_seconds` | 2.074741055024788 | 2.0942500620149076 |
| `observations[bad-079].areas[1].seconds` | 2.295992920990102 | 2.301969621970784 |
| `observations[bad-079].judge_seconds` | 2.4504475299618207 | 2.4512391019961797 |
| `observations[bad-080].areas[1].seconds` | 11.033962052024435 | 11.040181140997447 |
| `observations[bad-080].judge_seconds` | 11.112149277003482 | 11.113228906993754 |
| `observations[bad-081].judge_seconds` | 0.0006358879618346691 | 0.0006327779847197235 |
| `observations[bad-082].areas[1].seconds` | 2.094210888026282 | 2.093807004042901 |
| `observations[bad-082].judge_seconds` | 2.1557200319948606 | 2.1531117629492655 |
| `observations[bad-083].areas[1].seconds` | 2.4772179989959113 | 2.4764288389706053 |
| `observations[bad-083].judge_seconds` | 2.5431286380044185 | 2.543082125019282 |
| `observations[bad-084].areas[1].seconds` | 2.403851039998699 | 2.401478983985726 |
| `observations[bad-084].judge_seconds` | 2.4681182139902376 | 2.462330209033098 |
| `observations[bad-085].areas[1].seconds` | 10.806272608053405 | 10.802954552986193 |
| `observations[bad-085].judge_seconds` | 10.855827449995559 | 10.851180226018187 |
| `observations[bad-086].areas[1].seconds` | 2.2786250520148315 | 2.2755536869517528 |
| `observations[bad-086].judge_seconds` | 2.3385903169983067 | 2.3340817550197244 |
| `observations[bad-087].areas[1].seconds` | 2.2959775009658188 | 2.2860457620117813 |
| `observations[bad-087].judge_seconds` | 2.3852320450241677 | 2.373412909975741 |
| `observations[bad-088].areas[1].seconds` | 2.156178748991806 | 2.151303844002541 |
| `observations[bad-088].judge_seconds` | 2.210851277981419 | 2.20471392897889 |
| `observations[bad-089].areas[1].seconds` | 2.41249603102915 | 2.40342840005178 |
| `observations[bad-089].judge_seconds` | 2.632171728007961 | 2.6160974460071884 |
| `observations[bad-090].areas[1].seconds` | 2.299453188024927 | 2.294555767031852 |
| `observations[bad-090].judge_seconds` | 2.4191796790109947 | 2.4132112320512533 |
| `observations[bad-091].areas[1].seconds` | 2.1100431800005026 | 2.1047455390216783 |
| `observations[bad-091].judge_seconds` | 2.176526147988625 | 2.171201392018702 |
| `observations[bad-092].areas[1].seconds` | 2.1805325790192 | 2.188143672014121 |
| `observations[bad-092].judge_seconds` | 2.2612821819493547 | 2.266562369011808 |
| `observations[bad-093].areas[1].seconds` | 2.079103655007202 | 2.08301510597812 |
| `observations[bad-093].judge_seconds` | 2.166199778963346 | 2.1698616039939225 |
| `observations[bad-094].areas[1].seconds` | 4.845000783039723 | 4.85458371299319 |
| `observations[bad-094].judge_seconds` | 4.896106552041601 | 4.905397265974898 |
| `observations[bad-095].areas[1].seconds` | 10.84840246400563 | 10.838772675953805 |
| `observations[bad-095].judge_seconds` | 10.951199504022952 | 10.941809137002565 |
| `observations[bad-096].areas[1].seconds` | 11.012675933015998 | 11.011448444973212 |
| `observations[bad-096].judge_seconds` | 11.06305534800049 | 11.062218450999353 |
| `observations[bad-097].areas[1].seconds` | 2.1339798769913614 | 2.127294150996022 |
| `observations[bad-097].judge_seconds` | 2.1969835280324332 | 2.189632845984306 |
| `observations[bad-098].areas[1].seconds` | 2.044598456006497 | 2.0404508330393583 |
| `observations[bad-098].judge_seconds` | 2.0940542750176974 | 2.0899537000223063 |
| `observations[bad-099].areas[1].seconds` | 2.1365413360181265 | 2.1349196980008855 |
| `observations[bad-099].judge_seconds` | 2.2412814449635334 | 2.2334863339783624 |
| `observations[good-0011].areas[1].seconds` | 2.117626257997472 | 2.118701235973276 |
| `observations[good-0011].judge_seconds` | 2.1603629869641736 | 2.1590263619436882 |
| `observations[good-0013].judge_seconds` | 0.00019142800010740757 | 0.00015315302880480886 |
| `observations[good-0016].judge_seconds` | 0.00022091798018664122 | 0.0004007680108770728 |
| `observations[good-0024].judge_seconds` | 0.00038898602360859513 | 0.00041125400457531214 |
| `observations[good-0026].areas[1].seconds` | 2.1064952299930155 | 2.0967507130117156 |
| `observations[good-0026].judge_seconds` | 2.1535362169961445 | 2.1425972339930013 |
| `observations[good-0027].judge_seconds` | 0.0001981870154850185 | 0.0001700569991953671 |
| `observations[good-0046].judge_seconds` | 0.00021546497009694576 | 0.0003812030190601945 |
| `observations[good-0100].judge_seconds` | 0.00019210699247196317 | 0.00016204803250730038 |
| `observations[good-0107].judge_seconds` | 0.0026237020501866937 | 0.002905464032664895 |
| `observations[good-0159].judge_seconds` | 0.0004693499649874866 | 0.00047306501073762774 |
| `observations[good-0168].judge_seconds` | 0.00042078900150954723 | 0.000372720998711884 |
| `observations[good-0170].judge_seconds` | 0.0002529470366425812 | 0.00015267496928572655 |
| `observations[good-0172].judge_seconds` | 0.0003939229645766318 | 0.0003956380533054471 |
| `observations[good-0174].judge_seconds` | 0.0004533749888651073 | 0.00047262897714972496 |
| `observations[good-0178].judge_seconds` | 0.0004885050002485514 | 0.0004683000151999295 |
| `observations[good-0187].judge_seconds` | 0.0003683710237964988 | 0.0002199860173277557 |
| `observations[good-0196].judge_seconds` | 0.0004017789615318179 | 0.000366823049262166 |
| `observations[good-0208].judge_seconds` | 0.00019537605112418532 | 0.0004927209811285138 |
| `observations[good-0214].judge_seconds` | 0.00042033300269395113 | 0.0004033500445075333 |
| `observations[good-0215].judge_seconds` | 0.0006011910154484212 | 0.0005996669642627239 |
| `observations[good-0237].judge_seconds` | 0.00043236499186605215 | 0.0004637099918909371 |
| `observations[good-0261].judge_seconds` | 0.000423867953941226 | 0.00042923801811411977 |
| `observations[good-0286].judge_seconds` | 0.00043418502900749445 | 0.0004291690420359373 |
| `observations[good-0294].judge_seconds` | 0.0002253680140711367 | 0.0003932829713448882 |
| `observations[good-0297].judge_seconds` | 0.00019848899682983756 | 0.00016255502123385668 |
| `observations[good-0303].judge_seconds` | 0.0004561039968393743 | 0.0004558750079013407 |
| `observations[good-0306].judge_seconds` | 0.0003764780121855438 | 0.0003743079723790288 |
| `observations[good-0320].areas[1].seconds` | 2.3187005200306885 | 2.314666945952922 |
| `observations[good-0320].judge_seconds` | 2.3609476769925095 | 2.3569213380105793 |
| `observations[good-0333].judge_seconds` | 0.00020108796888962388 | 0.00016723101725801826 |
| `observations[good-0363].judge_seconds` | 0.0004081029910594225 | 0.0004102929960936308 |
| `observations[good-0377].judge_seconds` | 0.0004796020220965147 | 0.00047861499479040504 |
| `observations[good-0394].judge_seconds` | 0.0004382890183478594 | 0.0004118689685128629 |
| `observations[good-0400].judge_seconds` | 0.0002856419887393713 | 0.00036205799551680684 |
| `observations[good-0402].judge_seconds` | 0.000236822001170367 | 0.00042024400318041444 |
| `observations[good-0417].judge_seconds` | 0.0006077259895391762 | 0.0006076680147089064 |
| `observations[good-0423].areas[1].seconds` | 2.036064373969566 | 2.024596097005997 |
| `observations[good-0423].judge_seconds` | 2.0856792059494182 | 2.0731721589691006 |
| `observations[good-0427].judge_seconds` | 0.00020043697440996766 | 0.00017122301505878568 |
| `observations[good-0457].judge_seconds` | 0.0001861949567683041 | 0.0001604710123501718 |
| `observations[good-0469].judge_seconds` | 0.00026453897589817643 | 0.00037959596375003457 |
| `observations[good-0479].judge_seconds` | 0.0004065289977006614 | 0.0004193240310996771 |
| `observations[good-0483].judge_seconds` | 0.00048337498446926475 | 0.000363041996024549 |
| `observations[good-0484].judge_seconds` | 0.0005514320218935609 | 0.0005273999995552003 |
| `observations[good-0488].judge_seconds` | 0.00038005399983376265 | 0.0002178500290028751 |
| `observations[good-0490].judge_seconds` | 0.0004783649928867817 | 0.0004019819898530841 |
| `observations[good-0514].judge_seconds` | 0.0004380090394988656 | 0.0004348380025476217 |
| `observations[good-0518].judge_seconds` | 0.0004045589594170451 | 0.0003909869701601565 |
| `observations[good-0520].judge_seconds` | 0.00019199401140213013 | 0.0001492940355092287 |
| `observations[good-0525].judge_seconds` | 0.000267568975687027 | 0.00037239299854263663 |
| `observations[good-0545].judge_seconds` | 0.00014362699585035443 | 0.00021575199207291007 |
| `observations[good-0552].judge_seconds` | 0.00020895100897178054 | 0.00016787200001999736 |
| `observations[good-0569].judge_seconds` | 0.0004163339617662132 | 0.00039458199171349406 |
| `observations[good-0615].areas[1].seconds` | 2.380560746008996 | 2.373838654020801 |
| `observations[good-0615].judge_seconds` | 2.4319411009782925 | 2.4181410550372675 |
| `observations[good-0617].judge_seconds` | 0.0004354050033725798 | 0.00043425901094451547 |
| `observations[good-0619].judge_seconds` | 0.0003857039846479893 | 0.0004054579767398536 |
| `observations[good-0621].judge_seconds` | 0.00022612797329202294 | 0.0004138479707762599 |
| `observations[good-0629].judge_seconds` | 0.0004513190360739827 | 0.00044308596989139915 |
| `observations[good-0631].judge_seconds` | 0.0002660529571585357 | 0.00016253499779850245 |
| `observations[good-0648].judge_seconds` | 0.0004539939691312611 | 0.00044031802099198103 |
| `observations[good-0654].judge_seconds` | 0.000362850958481431 | 0.00036026700399816036 |
| `observations[good-0657].judge_seconds` | 0.0006085929926484823 | 0.0005901780095882714 |
| `observations[good-0659].judge_seconds` | 0.0004518389469012618 | 0.00047377898590639234 |
| `observations[good-0674].judge_seconds` | 0.00020193099044263363 | 0.00017606804613023996 |
| `observations[good-0684].judge_seconds` | 0.0004081730148755014 | 0.000420618976932019 |
| `observations[good-0685].judge_seconds` | 0.0002532689832150936 | 0.00015616900054737926 |
| `observations[good-0688].areas[1].seconds` | 2.036279015999753 | 2.0462231129640713 |
| `observations[good-0688].judge_seconds` | 2.0789378919871524 | 2.090796156961005 |
| `observations[good-0690].judge_seconds` | 0.00047443900257349014 | 0.0004495750181376934 |
| `observations[good-0694].judge_seconds` | 0.00042532902443781495 | 0.0004043930093757808 |
| `observations[good-0705].judge_seconds` | 0.00020071800099685788 | 0.00037648796569556 |
| `observations[good-0725].judge_seconds` | 0.00041041302029043436 | 0.00040759803960099816 |
| `observations[good-0730].judge_seconds` | 0.00039299397030845284 | 0.00040782702853903174 |
| `observations[good-0735].judge_seconds` | 0.00039485201705247164 | 0.0003946280339732766 |
| `observations[good-0739].judge_seconds` | 0.0004102579550817609 | 0.00040256703505292535 |
| `observations[good-0751].judge_seconds` | 0.0004831700352951884 | 0.0005200399900786579 |
| `observations[good-0755].judge_seconds` | 0.00019016099395230412 | 0.000159173971042037 |
| `observations[good-0764].judge_seconds` | 0.000414007983636111 | 0.00041982298716902733 |
| `observations[good-0768].judge_seconds` | 0.00018493301467970014 | 0.00016067898832261562 |
| `observations[good-0779].judge_seconds` | 0.000430108979344368 | 0.0004104530089534819 |
| `observations[good-0784].areas[1].seconds` | 2.2759084400022402 | 2.2705917339771986 |
| `observations[good-0784].judge_seconds` | 2.3183186349924654 | 2.3128527930239215 |
| `observations[good-0796].judge_seconds` | 0.0006684079999104142 | 0.0005892579792998731 |
| `observations[good-0797].judge_seconds` | 0.00045303197111934423 | 0.0004360229941084981 |
| `observations[good-0800].judge_seconds` | 0.0001860830234363675 | 0.0001647649914957583 |
| `observations[good-0804].judge_seconds` | 0.00019779597641900182 | 0.0001634230138733983 |
| `observations[good-0811].judge_seconds` | 0.0005740920314565301 | 0.0005965520394966006 |
| `observations[good-0844].judge_seconds` | 0.0006447079940699041 | 0.0005976140382699668 |
| `observations[good-0869].judge_seconds` | 0.0005911949556320906 | 0.0006135189905762672 |
| `observations[good-0871].areas[1].seconds` | 2.07016811799258 | 2.0677810490014963 |
| `observations[good-0871].judge_seconds` | 2.1341272279969417 | 2.1332395300269127 |
| `observations[good-0892].judge_seconds` | 0.00040736800292506814 | 0.00036313204327598214 |
| `observations[good-0900].judge_seconds` | 0.0004536749911494553 | 0.00041852000867947936 |
| `observations[good-0920].judge_seconds` | 0.00042275903979316354 | 0.00042658200254663825 |
| `observations[good-0923].judge_seconds` | 0.00019284000154584646 | 0.00016684603178873658 |
| `observations[good-0935].judge_seconds` | 0.0004695130046457052 | 0.00046492600813508034 |
| `observations[good-0940].judge_seconds` | 0.0004293820238672197 | 0.000404032994993031 |
| `observations[good-0952].judge_seconds` | 8.714100113138556e-05 | 0.00016882596537470818 |
| `observations[good-0957].judge_seconds` | 0.0004725850303657353 | 0.000481113966088742 |
| `observations[good-0964].judge_seconds` | 0.0003742179833352566 | 0.00029918202199041843 |
| `observations[good-0971].judge_seconds` | 0.0004046820104122162 | 0.0004139330121688545 |
| `observations[good-0974].judge_seconds` | 0.0006331080221571028 | 0.0005207470385357738 |
| `observations[good-0977].judge_seconds` | 0.0005787610425613821 | 0.0006490530213341117 |
| `observations[good-0990].areas[1].seconds` | 2.190615458996035 | 2.1817980720079504 |
| `observations[good-0990].judge_seconds` | 2.2377792689949274 | 2.225159906956833 |
| `observations[good-0994].judge_seconds` | 0.0003689930308610201 | 0.00021422002464532852 |
| `observations[good-1001].judge_seconds` | 0.0003823129809461534 | 0.0003905479679815471 |

## Figure 7: `report_seconds`, `whole_seconds`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `report_seconds` | 0.05935861903708428 | 0.06030521000502631 |
| `whole_seconds` | 295.6598059369717 | 296.69226150604663 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `report_seconds` | 0.049923538987059146 | 0.06318082101643085 |
| `whole_seconds` | 319.8182835599873 | 319.7247968229931 |

## Figure 7: `times`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `times.anomaly_seconds_per_image.pcb1` | 0.09873797918990021 | 0.09931010073487415 |
| `times.flagged_image_seconds.maximum` | 3.478405427186226 | 3.5001054427280907 |
| `times.flagged_image_seconds.mean` | 2.360803819115303 | 2.3633239567639164 |
| `times.flagged_image_seconds.minimum` | 1.9835311631890362 | 1.9965356626940776 |
| `times.flagged_image_seconds.p50` | 2.330110382170824 | 2.3399015867777053 |
| `times.flagged_image_seconds.p95` | 2.7329322146528283 | 2.7330393207535963 |
| `times.judge_stage_seconds` | 251.23728906101314 | 251.45052091800608 |
| `times.measure_and_draw_seconds.maximum` | 0.4542111369664781 | 0.4565035969717428 |
| `times.measure_and_draw_seconds.mean` | 0.08704055659263185 | 0.0877222387300519 |
| `times.measure_and_draw_seconds.minimum` | 0.0384935419424437 | 0.03767299198079854 |
| `times.measure_and_draw_seconds.p50` | 0.052822251978795975 | 0.052886082034092396 |
| `times.measure_and_draw_seconds.p95` | 0.23092500396887772 | 0.23406304098898545 |
| `times.parse_seconds` | 7.178763791976962 | 7.142659176024608 |
| `times.vlm_seconds_per_area.maximum` | 2.9840716260368936 | 2.973880284000188 |
| `times.vlm_seconds_per_area.mean` | 2.1750252833327717 | 2.1762916172989897 |
| `times.vlm_seconds_per_area.minimum` | 1.8369172569946386 | 1.8508482170291245 |
| `times.vlm_seconds_per_area.p50` | 2.127748769009486 | 2.119459812005516 |
| `times.vlm_seconds_per_area.p95` | 2.5560369419981726 | 2.557798328984063 |
| `times.vlm_seconds_per_flagged_image.maximum` | 2.9840716260368936 | 2.973880284000188 |
| `times.vlm_seconds_per_flagged_image.mean` | 2.1750252833327717 | 2.1762916172989897 |
| `times.vlm_seconds_per_flagged_image.minimum` | 1.8369172569946386 | 1.8508482170291245 |
| `times.vlm_seconds_per_flagged_image.p50` | 2.127748769009486 | 2.119459812005516 |
| `times.vlm_seconds_per_flagged_image.p95` | 2.5560369419981726 | 2.557798328984063 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `times.anomaly_seconds_per_image.pcb4` | 0.098989877233569 | 0.09902931031347044 |
| `times.flagged_image_seconds.maximum` | 11.21113915423705 | 11.212258217307225 |
| `times.flagged_image_seconds.mean` | 2.70021999125106 | 2.701330911163372 |
| `times.flagged_image_seconds.minimum` | 2.088588132255998 | 2.097679245318703 |
| `times.flagged_image_seconds.p50` | 2.340312824724995 | 2.352319697795154 |
| `times.flagged_image_seconds.p95` | 2.7089008327406443 | 2.696872926073682 |
| `times.judge_stage_seconds` | 275.86757179000415 | 275.98250568204094 |
| `times.measure_and_draw_seconds.maximum` | 0.31820290005998686 | 0.3179532110225409 |
| `times.measure_and_draw_seconds.mean` | 0.09333362667393028 | 0.09236010869872703 |
| `times.measure_and_draw_seconds.minimum` | 0.04224715696182102 | 0.040325125970412046 |
| `times.measure_and_draw_seconds.p50` | 0.06985964946215972 | 0.06780221650842577 |
| `times.measure_and_draw_seconds.p95` | 0.2554113492369652 | 0.2547707232151879 |
| `times.parse_seconds` | 6.18039052397944 | 5.854899270052556 |
| `times.vlm_seconds_per_area.maximum` | 11.033962052024435 | 11.040181140997447 |
| `times.vlm_seconds_per_area.mean` | 2.50789648734356 | 2.5099414921511745 |
| `times.vlm_seconds_per_area.minimum` | 1.9397805850021541 | 1.9459683500463143 |
| `times.vlm_seconds_per_area.p50` | 2.1347779684874695 | 2.132670663500903 |
| `times.vlm_seconds_per_area.p95` | 2.461037507004221 | 2.458178729240899 |
| `times.vlm_seconds_per_flagged_image.maximum` | 11.033962052024435 | 11.040181140997447 |
| `times.vlm_seconds_per_flagged_image.mean` | 2.50789648734356 | 2.5099414921511745 |
| `times.vlm_seconds_per_flagged_image.minimum` | 1.9397805850021541 | 1.9459683500463143 |
| `times.vlm_seconds_per_flagged_image.p50` | 2.1347779684874695 | 2.132670663500903 |
| `times.vlm_seconds_per_flagged_image.p95` | 2.461037507004221 | 2.458178729240899 |

## Figure 8: `inspector`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `inspector.minutes_all_parts` | 11.765913593332517 | 11.76531184973331 |
| `inspector.minutes_by_part.pcb1` | 11.765913593332517 | 11.76531184973331 |
| `inspector.parse_seconds` | 7.178763791976962 | 7.142659176024608 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `inspector.minutes_all_parts` | 11.782835907616148 | 11.777411053384034 |
| `inspector.minutes_by_part.pcb4` | 11.782835907616148 | 11.777411053384034 |
| `inspector.parse_seconds` | 6.18039052397944 | 5.854899270052556 |

## Figure 9: `memory`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `memory.by_stage.judge.anomaly_card_mib` | 962 | 964 |
| `memory.by_stage.report.judge_card_mib` | 29784 | 29786 |
| `memory.by_stage.report.samples` | 1 | 2 |
| `memory.readings.path` | results/stage2/batch/pcb1.cards.20261107T115146Z.csv | results/stage2/batch/pcb1.cards.20261107T120325Z.csv |
| `memory.readings.sha256` | 7f6ac7d898a67886041ae21c1b50e734eb377fefaee4dfb285e1dfc34541f8d6 | c782bc8a55b788f6ccf72691f49eed70e74fe14f4e9d71b8d96302e30e3629a4 |
| `memory.whole.samples` | 60 | 61 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `memory.by_stage.score.anomaly_card_mib` | 2595 | 2596 |
| `memory.readings.path` | results/stage2/batch/pcb4.cards.20261107T115648Z.csv | results/stage2/batch/pcb4.cards.20261107T120829Z.csv |
| `memory.readings.sha256` | 6127c1bdec8fd9fd29cfe21b4fc359474b6fe4fd63e1749b9a8cc9245c99df13 | 3ff4efa67c62b2723533e752a14ac3ed9129051227fb98f20f6516b56c1fafff |
| `memory.whole.anomaly_card_mib` | 2595 | 2596 |

## How the judge was asked: `judge`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `judge.cold.server_log.path` | results/stage2/batch/pcb1.server-log.20261107T115146Z.txt | results/stage2/batch/pcb1.server-log.20261107T120325Z.txt |
| `judge.cold.server_log.sha256` | fc840797e515d558e1da7b336b6f31308e4fd8c68d6a3abaa39ac8162b16283b | 2af15ba2a5b5dba7e4f551048e7a38fc505d2d0c9b3d1e52aee25149697e3c22 |
| `judge.warm_up.seconds` | 1.970417506992817 | 1.9800271000131033 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `judge.cold.server_log.path` | results/stage2/batch/pcb4.server-log.20261107T115648Z.txt | results/stage2/batch/pcb4.server-log.20261107T120829Z.txt |
| `judge.cold.server_log.sha256` | e1be12e4e8181d04b60a70ea12bb71a536dd6418cb7830dcb8f5eb2675bb3b6f | 950c8c14fdf1d4a899ffd8c3e344c99b27067093a5733ee336e53893824b14ff |
| `judge.warm_up.seconds` | 2.243387876020279 | 2.26329002098646 |

## The anomaly model's stage: `run`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `run.inference_seconds` | 19.747595837980043 | 19.862020146974828 |
| `run.load_seconds` | 2.3963176399702206 | 2.532287522975821 |
| `run.seconds_per_image` | 0.09873797918990021 | 0.09931010073487415 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `run.inference_seconds` | 19.89696532394737 | 19.90489137300756 |
| `run.load_seconds` | 2.4735988110187463 | 2.4707055439939722 |
| `run.seconds_per_image` | 0.098989877233569 | 0.09902931031347044 |

## The cards and the report: `report`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `report.run_bytes` | 121358808 | 121358812 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `report.run_bytes` | 121613581 | 121613577 |

## The specification: `specification`, `clause_table`

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `specification.parse_seconds` | 7.178763791976962 | 7.142659176024608 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `specification.parse_seconds` | 6.18039052397944 | 5.854899270052556 |

## What the record is made of

### pcb1

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `measured_at` | 2026-11-07T11:56:45+00:00 | 2026-11-07T12:08:25+00:00 |

### pcb4

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `measured_at` | 2026-11-07T12:02:12+00:00 | 2026-11-07T12:13:52+00:00 |
