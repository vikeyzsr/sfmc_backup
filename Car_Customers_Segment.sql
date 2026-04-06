-- Data Cloud Segment: Car Customers
-- Equivalent of MC Engagement SQL: select [coustemer id], [email id], [first name], [last name], [brand name], varient, [delivery date] from car
--
-- This segment selects all Unified Individuals who have at least one order
-- in OrdersHistory (the Data Cloud equivalent of the MC "car" data extension).
--
-- Segment entity: ssot__Individual__dlm
-- Related object: OrdersHistory__dlm (joined via Individual_Id__c)

SELECT DISTINCT
    i."ssot__Id__c" AS "Individual Id"
FROM
    "ssot__Individual__dlm" i
    JOIN "OrdersHistory__dlm" o
        ON i."ssot__Id__c" = o."Individual_Id__c"
