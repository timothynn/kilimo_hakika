-- =============================================================================
-- DEVELOPMENT FIXTURE - NOT PRODUCTION POLICY DATA
--
-- The rules, allocation formula and document requirements below are traced to
-- NCPB's own published FAQ and to the Ministry's 2025 NFSP launch notice, and
-- are believed correct. Three things are NOT verified and are marked with
-- source_type = 'UNVERIFIED':
--
--   1. SEED-SEASON-WINDOW  - the season start/end dates are invented so that
--                            local development resolves a season "today".
--   2. SEED-LEASED-LAND    - the chief's-letter requirement for leased land is
--                            from the product brief, not a traced circular.
--   3. PRESS-PRICES-2025   - the per-product price list came from press
--                            reporting, not from the season circular.
--
-- kh.publish_rule_pack() will REFUSE to publish a pack built from this fixture
-- for exactly those reasons. That is deliberate. Before production, replace
-- every SEED-* and PRESS-* citation with the gazette notice or MOALD circular,
-- then publish. Until then the API runs off database/scheme_rules.json.
--
-- Swahili strings are a first pass and need native-speaker review before any
-- farmer sees them.
-- =============================================================================

begin;

-- ---------------------------------------------------------------------------
-- Citations. One row per discrete published statement, so a rule points at the
-- exact sentence that justifies it.
-- ---------------------------------------------------------------------------

insert into kh.citation (id, title, issuer, source_type, reference, url, issued_on, retrieved_on, verbatim_extract, notes) values
 ('NCPB-FAQ-2022-10-Q2', 'Government Subsidized Fertilizer Program FAQs, Q2', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q2',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'A duly registered farmer whose details are in the register provided to NCPB qualifies.', null),

 ('NCPB-FAQ-2022-10-Q3', 'Government Subsidized Fertilizer Program FAQs, Q3', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q3',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'appear in person at the nearest NCPB depot with your original identity card', null),

 ('NCPB-FAQ-2022-10-Q4', 'Government Subsidized Fertilizer Program FAQs, Q4', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q4',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'buy subsidized fertilizer on behalf of somebody else - not acceptable', null),

 ('NCPB-FAQ-2022-10-Q7', 'Government Subsidized Fertilizer Program FAQs, Q7', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q7',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'from any of the nearest NCPB depots within the county where you are registered', null),

 ('NCPB-FAQ-2022-10-Q8', 'Government Subsidized Fertilizer Program FAQs, Q8', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q8',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'two bags each for planting and top dressing per acre; combined maximum of 100 bags per season',
  'Worked examples in the source: 3 acres -> 12 bags, 15 acres -> 60 bags, over 25 acres -> 100 bags. These are the golden test cases.'),

 ('NCPB-FAQ-2022-10-Q10', 'Government Subsidized Fertilizer Program FAQs, Q10', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q10',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'Cash payments at the depot shall NOT be accepted.',
  'Payment is via the NCPB M-Pesa till displayed at the depot or a bank deposit. Kilimo Hakika only states this; it never handles a payment.'),

 ('NCPB-FAQ-2022-10-Q11', 'Government Subsidized Fertilizer Program FAQs, Q11', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q11',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'farmers are required to pay before collecting the fertilizer', null),

 ('NCPB-FAQ-2022-10-Q12', 'Government Subsidized Fertilizer Program FAQs, Q12', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q12',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'you can buy what you need any time as long as the maximum allowed as per your acreage is not exceeded',
  'The cap is cumulative across the season. Kilimo Hakika cannot see prior draws, so it reports the season entitlement, not a remaining balance.'),

 ('NCPB-FAQ-2022-10-Q13', 'Government Subsidized Fertilizer Program FAQs, Q13', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q13',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'buy the fertilizer and resell to others - this is ILLEGAL', null),

 ('NCPB-FAQ-2022-10-Q15', 'Government Subsidized Fertilizer Program FAQs, Q15', 'National Cereals and Produce Board', 'AGENCY_FAQ', 'FAQ Q15',
  'https://ncpb.co.ke/wp-content/uploads/dlm_uploads/2022/10/FAQS-on-Subsidy-Fertilizers-October-2022.pdf',
  '2022-10-01', '2026-09-02',
  'All NCPB depots are open Monday to Friday from 8.00am to 5.00pm.', null),

 ('NCPB-QA-2022-05-SILOS', 'Question and Answer about NCPB', 'National Cereals and Produce Board', 'AGENCY_PUBLICATION', 'Corporate Q&A',
  'https://ncpb.co.ke/wp-content/uploads/2022/05/QUESTION-AND-ANSWER-ABOUT-NATIONAL-CEREALS-AND-PRODUCE-BOARD-DRAFT.pdf',
  '2022-05-01', '2026-09-02',
  'silo complexes located in Nairobi, Eldoret, Moi''s Bridge, Bungoma, Kisumu, Nakuru and Narok',
  'NCPB reports 110 depots across 46 counties. Only the silo complexes are seeded here; the full roster must be imported before launch.'),

 ('MOALD-NFSP-2025-LAUNCH', '2025 Long Rains National Fertilizer Subsidy Programme launch', 'Ministry of Agriculture and Livestock Development', 'AGENCY_PUBLICATION', 'NFSP 2025 launch notice',
  'https://kilimo.go.ke/cs-dr-andrew-karanja-has-presided-over-the-launch-of-the-2025-long-rains-national-fertilizer-subsidy-programme-nfsp-at-the-ncpb-gpc-depot-nairobi/',
  '2025-01-01', '2026-09-02',
  'subsidised fertilizer remains at Ksh 2,500 per 50-kg bag; registered farmers receive e-vouchers redeemed at NCPB depots and partner outlets',
  'Establishes the e-voucher as a gate condition and KIAMIS registration as the register of record.'),

 ('PRESS-PRICES-2025', 'Reported per-product subsidised fertiliser prices, 2025', 'Press reporting', 'PRESS', 'Multiple outlets',
  'https://www.the-star.co.ke/news/ground-check/2026-08-25-fertiliser-subsidy-inside-states-32m-bags-in-4-seasons',
  '2025-01-01', '2026-09-02',
  'DAP 2,500; CAN 2,875; Urea 3,500; NPK 3,275; MOP 1,775; Sulphate of Ammonia 2,220 per 50kg bag',
  'PRESS is not good enough for a statutory number. Replace with the season circular before publishing a pack.'),

 ('SEED-SEASON-WINDOW', 'Placeholder season window for local development', 'Kilimo Hakika', 'UNVERIFIED', null, null, null, '2026-09-02',
  null, 'Invented dates so a season resolves during development. Must be replaced with the gazetted programme window.'),

 ('SEED-LEASED-LAND', 'Leased-land proof requirement (from product brief)', 'Kilimo Hakika', 'UNVERIFIED', null, null, null, '2026-09-02',
  null, 'The product brief cites farmers turned away for a missing chief''s stamp on a land lease. Not yet traced to a circular, so it ships as an ADVISORY only.');

-- ---------------------------------------------------------------------------
-- Geography and depots
-- ---------------------------------------------------------------------------

insert into kh.county (code, name) values
 ('020','Kirinyaga'), ('026','Trans Nzoia'), ('027','Uasin Gishu'),
 ('032','Nakuru'), ('033','Narok'), ('039','Bungoma'),
 ('042','Kisumu'), ('047','Nairobi');

insert into kh.depot (code, name, county_code, kind, citation_id, notes) values
 ('NCPB-NAIROBI-GPC', 'Nairobi GPC Depot',  '047', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-ELDORET',     'Eldoret Depot',      '027', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-MOIS-BRIDGE', 'Moi''s Bridge Depot','026', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', 'County assignment needs confirming - Moi''s Bridge sits near the Trans Nzoia / Uasin Gishu boundary and the county decides the DEPOT_COUNTY_MATCH rule.'),
 ('NCPB-BUNGOMA',     'Bungoma Depot',      '039', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-KISUMU',      'Kisumu Depot',       '042', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-NAKURU',      'Nakuru Depot',       '032', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-NAROK',       'Narok Depot',        '033', 'SILO_COMPLEX', 'NCPB-QA-2022-05-SILOS', null),
 ('NCPB-SAGANA',      'Sagana Depot',       '020', 'DEPOT',        'NCPB-QA-2022-05-SILOS', null);

-- Monday to Friday, 08:00-17:00, everywhere.
insert into kh.depot_hours (depot_code, weekday, opens_at, closes_at, citation_id)
select d.code, w, time '08:00', time '17:00', 'NCPB-FAQ-2022-10-Q15'
from kh.depot d cross join generate_series(1,5) as w;

-- ---------------------------------------------------------------------------
-- Documents
-- ---------------------------------------------------------------------------

insert into kh.document (code, label_en, label_sw, issuer, how_to_obtain_en, how_to_obtain_sw, is_physical, sort_order) values
 ('NATIONAL_ID_ORIGINAL',
  'Original National ID card (not a photocopy)',
  'Kitambulisho halisi cha kitaifa (sio nakala)',
  'Department of Immigration and Citizen Services',
  'Replace a lost ID at your sub-county registration office. A waiting card is not accepted at the gate.',
  'Badilisha kitambulisho kilichopotea katika ofisi ya usajili ya kaunti ndogo. Kadi ya kusubiri haikubaliwi getini.',
  true, 10),

 ('FARMER_REGISTER_ENTRY',
  'Your name on the NCPB farmers register for this county',
  'Jina lako kwenye daftari la wakulima la NCPB la kaunti hii',
  'National Cereals and Produce Board',
  'Register free of charge at your County, Sub-county or Ward Agricultural Office.',
  'Jisajili bila malipo katika ofisi ya kilimo ya kaunti, kaunti ndogo au wodi.',
  false, 20),

 ('KIAMIS_REGISTRATION',
  'Farmer registration on KIAMIS',
  'Usajili wa mkulima kwenye KIAMIS',
  'Ministry of Agriculture and Livestock Development',
  'Register through an agricultural officer, or by dialling the subsidy USSD code and giving your land size.',
  'Jisajili kupitia afisa wa kilimo, au kwa kupiga namba ya USSD ya ruzuku na kutoa ukubwa wa shamba lako.',
  false, 30),

 ('EVOUCHER_CODE',
  'E-voucher code received by SMS',
  'Namba ya e-voucher uliyopokea kwa SMS',
  'Ministry of Agriculture and Livestock Development',
  'Issued by SMS once your registration is verified. Without the code the depot cannot serve you.',
  'Hutumwa kwa SMS baada ya usajili wako kuthibitishwa. Bila namba hiyo, depo haiwezi kukuhudumia.',
  true, 40),

 ('NON_CASH_PAYMENT_MEANS',
  'A way to pay without cash - M-Pesa on your own phone, or a bank deposit slip',
  'Njia ya kulipa bila pesa taslimu - M-Pesa kwa simu yako mwenyewe, au hati ya malipo ya benki',
  'National Cereals and Produce Board',
  'Cash is not accepted at the depot. Pay to the NCPB till number displayed at the depot, or deposit at the bank the depot manager names.',
  'Pesa taslimu hazikubaliwi deponi. Lipa kwa namba ya till ya NCPB iliyoonyeshwa deponi, au weka pesa benki aliyoitaja meneja wa depo.',
  true, 50),

 ('LAND_LEASE_AGREEMENT',
  'Signed land lease agreement',
  'Mkataba wa kukodisha shamba uliotiwa saini',
  'Land owner and tenant',
  'A written agreement signed by the land owner, showing the acreage you farm.',
  'Mkataba ulioandikwa na kutiwa saini na mwenye shamba, ukionyesha ukubwa wa shamba unalolima.',
  true, 60),

 ('CHIEF_LETTER',
  'Stamped letter from your Chief confirming you farm the land',
  'Barua yenye mhuri kutoka kwa Chifu ikithibitisha unalima shamba hilo',
  'Office of the Chief',
  'Ask your Chief or Assistant Chief. The letter must carry the office stamp, not only a signature.',
  'Muulize Chifu au Chifu Msaidizi. Barua lazima iwe na mhuri wa ofisi, sio saini pekee.',
  true, 70);

-- ---------------------------------------------------------------------------
-- Scheme, season, allocation, prices
-- ---------------------------------------------------------------------------

insert into kh.scheme (code, name, administering_body) values
 ('NFSP', 'National Fertilizer Subsidy Programme', 'Ministry of Agriculture and Livestock Development / NCPB');

insert into kh.scheme_season (scheme_code, code, label_en, label_sw, effective_from, effective_to, citation_id) values
 ('NFSP', '2026_SHORT_RAINS', '2026 Short Rains season', 'Msimu wa vuli 2026',
  '2026-08-01', '2027-01-31', 'SEED-SEASON-WINDOW');

insert into kh.allocation_rule (
  season_id, planting_bags_per_acre, topdress_bags_per_acre, max_total_bags,
  bag_weight_kg, rounding_mode, cap_split, min_acres, citation_id)
select id, 2, 2, 100, 50, 'FLOOR', 'PRO_RATA', 0.25, 'NCPB-FAQ-2022-10-Q8'
from kh.scheme_season where scheme_code = 'NFSP' and code = '2026_SHORT_RAINS';

insert into kh.fertilizer_type (code, name_en, name_sw, sort_order) values
 ('DAP',  'DAP (planting)',                'DAP (kupanda)',              10),
 ('NPK',  'NPK (planting)',                'NPK (kupanda)',              20),
 ('CAN',  'CAN (top dressing)',            'CAN (kukuzia)',              30),
 ('UREA', 'Urea (top dressing)',           'Urea (kukuzia)',             40),
 ('SA',   'Sulphate of Ammonia',           'Sulphate of Ammonia',        50),
 ('MOP',  'MOP (muriate of potash)',       'MOP (muriate of potash)',    60);

insert into kh.price (season_id, fertilizer_code, purpose, price_kes_per_bag, citation_id)
select s.id, v.code, v.purpose, v.price, v.citation
from kh.scheme_season s
cross join (values
  ('DAP',  'PLANTING', 2500.00, 'MOALD-NFSP-2025-LAUNCH'),
  ('NPK',  'PLANTING', 3275.00, 'PRESS-PRICES-2025'),
  ('CAN',  'TOPDRESS', 2875.00, 'PRESS-PRICES-2025'),
  ('UREA', 'TOPDRESS', 3500.00, 'PRESS-PRICES-2025'),
  ('SA',   'TOPDRESS', 2220.00, 'PRESS-PRICES-2025'),
  ('MOP',  'ANY',      1775.00, 'PRESS-PRICES-2025')
) as v(code, purpose, price, citation)
where s.scheme_code = 'NFSP' and s.code = '2026_SHORT_RAINS';

-- ---------------------------------------------------------------------------
-- Rules
--
-- A DOCUMENT rule fails when its document is not in the farmer's held set.
-- applies_when only decides whether the requirement is in play at all.
-- ---------------------------------------------------------------------------

insert into kh.rule (
  season_id, code, kind, document_code, applies_when, severity,
  message_en, message_sw, remedy_en, remedy_sw, citation_id, eval_order)
select s.id, v.code, v.kind, v.document_code, v.applies_when::jsonb, v.severity,
       v.message_en, v.message_sw, v.remedy_en, v.remedy_sw, v.citation_id, v.eval_order
from kh.scheme_season s
cross join (values

 ('DOC_NATIONAL_ID_ORIGINAL', 'DOCUMENT', 'NATIONAL_ID_ORIGINAL', null, 'BLOCKER',
  'You must hand over your original National ID at the depot counter. A photocopy or a waiting card will be refused.',
  'Lazima utoe kitambulisho chako halisi cha kitaifa kwenye kaunta ya depo. Nakala au kadi ya kusubiri itakataliwa.',
  'Do not travel without it.', 'Usisafiri bila kitambulisho hicho.',
  'NCPB-FAQ-2022-10-Q3', 10),

 ('DOC_FARMER_REGISTER_ENTRY', 'DOCUMENT', 'FARMER_REGISTER_ENTRY', null, 'BLOCKER',
  'Your name must already be in the NCPB farmers register. The depot cannot add you at the gate.',
  'Jina lako lazima liwe tayari kwenye daftari la wakulima la NCPB. Depo haiwezi kukuongeza getini.',
  'Register free of charge at your County, Sub-county or Ward Agricultural Office first.',
  'Jisajili bila malipo katika ofisi ya kilimo ya kaunti, kaunti ndogo au wodi kwanza.',
  'NCPB-FAQ-2022-10-Q2', 20),

 ('DOC_KIAMIS_REGISTRATION', 'DOCUMENT', 'KIAMIS_REGISTRATION', null, 'BLOCKER',
  'You must be registered on KIAMIS. The e-voucher is issued from that register.',
  'Lazima uwe umesajiliwa kwenye KIAMIS. E-voucher hutolewa kutoka daftari hilo.',
  'Register through your agricultural officer.', 'Jisajili kupitia afisa wako wa kilimo.',
  'MOALD-NFSP-2025-LAUNCH', 30),

 ('DOC_EVOUCHER_CODE', 'DOCUMENT', 'EVOUCHER_CODE', null, 'BLOCKER',
  'You need the e-voucher code sent to you by SMS. Without it the depot has nothing to redeem.',
  'Unahitaji namba ya e-voucher iliyotumwa kwako kwa SMS. Bila hiyo, depo haina kitu cha kukomboa.',
  'Check your SMS inbox before you travel. If no code has arrived, your registration is not yet verified.',
  'Angalia SMS zako kabla ya kusafiri. Kama namba haijafika, usajili wako haujathibitishwa.',
  'MOALD-NFSP-2025-LAUNCH', 40),

 ('DOC_NON_CASH_PAYMENT_MEANS', 'DOCUMENT', 'NON_CASH_PAYMENT_MEANS', null, 'BLOCKER',
  'Cash is not accepted at the depot, and you must pay before collecting. Carry a phone with M-Pesa, or pay in at the bank first.',
  'Pesa taslimu hazikubaliwi deponi, na lazima ulipe kabla ya kuchukua mzigo. Nenda na simu yenye M-Pesa, au lipa benki kwanza.',
  'Pay to the NCPB till number displayed at the depot, or to the bank account the depot manager gives you.',
  'Lipa kwa namba ya till ya NCPB iliyoonyeshwa deponi, au akaunti ya benki utakayopewa na meneja wa depo.',
  'NCPB-FAQ-2022-10-Q10', 50),

 ('ELIG_COLLECTING_IN_PERSON', 'ELIGIBILITY', null,
  '{"field":"collecting_in_person","eq":false}', 'BLOCKER',
  'You cannot buy subsidised fertiliser for somebody else. The registered farmer must come in person.',
  'Hauwezi kununua mbolea ya ruzuku kwa niaba ya mtu mwingine. Mkulima aliyesajiliwa lazima aje mwenyewe.',
  'The registered farmer must travel with their own ID.', 'Mkulima aliyesajiliwa lazima asafiri na kitambulisho chake.',
  'NCPB-FAQ-2022-10-Q4', 60),

 ('ELIG_DEPOT_COUNTY_MISMATCH', 'ELIGIBILITY', null,
  '{"all":[{"field":"registration_county_code","is_known":true},{"field":"registration_county_code","ne_field":"depot_county_code"}]}',
  'BLOCKER',
  'This depot is not in the county where you are registered. You can only collect within your registration county.',
  'Depo hii haiko katika kaunti uliyosajiliwa. Unaweza kuchukua mbolea tu katika kaunti yako ya usajili.',
  'Choose a depot inside your registration county.', 'Chagua depo iliyo katika kaunti yako ya usajili.',
  'NCPB-FAQ-2022-10-Q7', 70),

 ('ELIG_DEPOT_COUNTY_UNKNOWN', 'ELIGIBILITY', null,
  '{"field":"registration_county_code","is_known":false}', 'ADVISORY',
  'You can only be served in the county where you registered. Confirm this depot is in that county before you travel.',
  'Unaweza kuhudumiwa tu katika kaunti uliyosajiliwa. Hakikisha depo hii iko katika kaunti hiyo kabla ya kusafiri.',
  null, null,
  'NCPB-FAQ-2022-10-Q7', 80),

 ('TEMPORAL_DEPOT_CLOSED', 'TEMPORAL', null,
  '{"field":"depot_open_on_travel_date","eq":false}', 'BLOCKER',
  'The depot is closed on the day you plan to travel. Depots open Monday to Friday, 8.00am to 5.00pm.',
  'Depo imefungwa siku unayotaka kusafiri. Depo hufunguliwa Jumatatu hadi Ijumaa, saa 2 asubuhi hadi saa 11 jioni.',
  'Travel on a weekday and arrive before 5.00pm.', 'Safiri siku ya kazi na uwahi kabla ya saa 11 jioni.',
  'NCPB-FAQ-2022-10-Q15', 90),

 ('ADVISORY_LEASED_LAND_PROOF', 'DOCUMENT', 'CHIEF_LETTER',
  '{"field":"land_tenure","in":["LEASED","FAMILY_UNREGISTERED"]}', 'ADVISORY',
  'Farmers on leased or unregistered family land are often asked for a stamped letter from the Chief. Carry one if you can.',
  'Wakulima wanaolima shamba la kukodi au la familia lisilosajiliwa mara nyingi huombwa barua yenye mhuri kutoka kwa Chifu. Chukua moja ikiwezekana.',
  'Ask your Chief or Assistant Chief for a stamped letter.', 'Muulize Chifu au Chifu Msaidizi barua yenye mhuri.',
  'SEED-LEASED-LAND', 100),

 ('ADVISORY_LEASED_LAND_AGREEMENT', 'DOCUMENT', 'LAND_LEASE_AGREEMENT',
  '{"field":"land_tenure","eq":"LEASED"}', 'ADVISORY',
  'On leased land, carry the signed lease agreement showing the acreage you farm.',
  'Kwa shamba la kukodi, chukua mkataba uliotiwa saini ukionyesha ukubwa wa shamba unalolima.',
  'The stamp from the Chief usually goes on this agreement.', 'Mhuri wa Chifu huwekwa kwenye mkataba huu.',
  'SEED-LEASED-LAND', 105),

 ('ADVISORY_CUMULATIVE_CAP', 'LOGISTICS', null, null, 'ADVISORY',
  'The bag figure below is your whole entitlement for the season. If you have already collected some bags, subtract them yourself - this app cannot see your record.',
  'Idadi ya mifuko iliyo hapa chini ni haki yako yote ya msimu. Kama umechukua mifuko awali, punguza mwenyewe - programu hii haioni rekodi yako.',
  null, null,
  'NCPB-FAQ-2022-10-Q12', 110),

 ('ADVISORY_NO_RESALE', 'LOGISTICS', null, null, 'ADVISORY',
  'Reselling subsidised fertiliser is illegal.',
  'Kuuza tena mbolea ya ruzuku ni kinyume cha sheria.',
  null, null,
  'NCPB-FAQ-2022-10-Q13', 120)

) as v(code, kind, document_code, applies_when, severity,
       message_en, message_sw, remedy_en, remedy_sw, citation_id, eval_order)
where s.scheme_code = 'NFSP' and s.code = '2026_SHORT_RAINS';

commit;

-- Build the pack (publishing it will fail on the UNVERIFIED citations, by design):
--   select version, checksum from kh.build_rule_pack('NFSP','2026_SHORT_RAINS','NFSP-2026_SHORT_RAINS-0001');
--   select kh.publish_rule_pack('NFSP-2026_SHORT_RAINS-0001');   -- expected to raise
