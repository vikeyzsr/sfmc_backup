/*
 * Competitive Product Assortment - Calculated Insight
 *
 * Identifies competitive (non-Goodyear) products observed on dealer websites
 * and creates Assortment / Assortment Item records per Common Owner + Brand + Product Line.
 *
 * ASSUMPTIONS (review and adjust before deploying):
 *   1. Competitive products DMO table name: Competitive_Product_Observances__dlm
 *   2. Website-to-Common-Owner mapping DMO table name: Website_Common_Owner_Mapping__dlm
 *   3. Common_Owner__c on the mapping table is an Account Number
 *      joining to Common_Owner_Hierarchy__cio.COAccountNumber__c
 *   4. product_line__c is free text (not joined to ssot__Product__dlm)
 *   5. External IDs prefixed with 'COMP~' to avoid collision with Goodyear assortment keys
 *   6. Same Assortment / Assortment Item Record Type IDs as Goodyear — update if different
 *   7. Same POC account filter as Goodyear CI — remove or update for production
 */

SELECT
    IFNULL(coh.COAccountId__c, coh.AccountId__c)           AS CommonOwnerCRMAccountId__c,
    IFNULL(co.AccountName__c, coh.AccountName__c)           AS CommonOwnerName__c,
    cp.brand__c                                              AS Brand__c,
    cp.product_line__c                                       AS ProductLine__c,
    MAX(cp.yearmonth__c)                                     AS LastObservanceDate__c,

    FIRST('012TI0000045SZHYA2')                              AS AssortmentRecordTypeId__c,
    FIRST('012TI0000045TOrYAM')                              AS AssortmentItemRecordTypeId__c,
    FIRST('Active')                                          AS AssortmentItemStatus__c,

    FIRST(CONCAT(
        'COMP~',
        IFNULL(coh.COAccountId__c, coh.AccountId__c),
        '~',
        cp.brand__c
    ))                                                       AS AssortmentExternalId__c,

    FIRST(CONCAT(
        IFNULL(co.AccountName__c, coh.AccountName__c),
        ' - ',
        cp.brand__c,
        ' (Competitive)'
    ))                                                       AS AssortmentName__c,

    FIRST(CONCAT(
        'COMP~',
        IFNULL(coh.COAccountId__c, coh.AccountId__c),
        '~',
        cp.brand__c,
        '~',
        cp.product_line__c
    ))                                                       AS AssortmentItemExternalId__c,

    SUM(cp.observances__c)                                   AS TotalObservances__c

FROM Competitive_Product_Observances__dlm cp                 /* << UPDATE table name */

INNER JOIN Website_Common_Owner_Mapping__dlm wcm             /* << UPDATE table name */
        ON cp.website__c = wcm.WEBSITE__c

INNER JOIN Common_Owner_Hierarchy__cio coh
        ON wcm.Common_Owner__c = coh.COAccountNumber__c     /* << UPDATE if Common_Owner__c is an Account ID, not Number */

INNER JOIN ssot__Account__dlm acct
        ON coh.AccountId__c  = acct.ssot__Id__c
       AND acct.KQ_Id__c     = 'CRM'
       AND acct.RecordTypeId__c = '012TI000000ltFZYAY'       /* Business Account */

LEFT OUTER JOIN (
    SELECT ssot__Account__dlm.ssot__Id__c   AS AccountId__c,
           ssot__Account__dlm.ssot__Name__c AS AccountName__c
      FROM ssot__Account__dlm
     WHERE ssot__Account__dlm.KQ_Id__c          = 'CRM'
       AND ssot__Account__dlm.RecordTypeId__c   = '012TI000000ltFZYAY'  /* Business Account */
       AND ssot__Account__dlm.ERP_Classification__c = 'Common Owner'
) co ON coh.COAccountId__c = co.AccountId__c

/* Exclude competitive items that were previously set to Inactive */
LEFT OUTER JOIN Product_Assortment_Item__dlm pai
        ON CONCAT(
               'COMP~',
               IFNULL(coh.COAccountId__c, coh.AccountId__c),
               '~',
               cp.brand__c,
               '~',
               cp.product_line__c
           ) = pai.Assortment_Item_External_Id__c
       AND pai.Status__c = 'Inactive'

WHERE cp.yearmonth__c >= CAST(DATE_ADD(CURRENT_DATE(), -365) AS TIMESTAMP)
  AND cp.observances__c > 0
  AND coh.AccountType__c <> 'Associate Dealer'
  AND pai.Id__c IS NULL

  /* POC Filter — remove for production rollout */
  AND IFNULL(coh.COAccountId__c, coh.AccountId__c) IN (
        '001TI00000WbZxfYAF',
        '001TI00000WbZvuYAF',
        '001TI00000QCtD5YAL',
        '001TI00000WbZvzYAF',
        '001TI00000WbZxXYAV',
        '001TI00000WbZwZYAV'
      )

GROUP BY
    IFNULL(coh.COAccountId__c, coh.AccountId__c),
    IFNULL(co.AccountName__c, coh.AccountName__c),
    cp.brand__c,
    cp.product_line__c
