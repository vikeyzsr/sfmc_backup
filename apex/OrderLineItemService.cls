public with sharing class OrderLineItemService {

    @InvocableMethod(label='Get Order Line Items'
                     description='Fetches line items from Data Cloud for a given Order ID'
                     callout=true)
    public static List<List<OrderLineItemRA>> getLineItems(List<String> orderIds) {
        List<List<OrderLineItemRA>> allResults = new List<List<OrderLineItemRA>>();

        for (String orderId : orderIds) {
            allResults.add(queryLineItems(orderId));
        }

        return allResults;
    }

    private static List<OrderLineItemRA> queryLineItems(String orderId) {
        List<OrderLineItemRA> items = new List<OrderLineItemRA>();

        String sql = 'SELECT "ProductID__c", "ProductName__c", "UnitPrice__c" ' +
                     'FROM "Order_List_Items__dll" ' +
                     'WHERE "OrderID__c" = \'' + String.escapeSingleQuotes(orderId) + '\'';

        HttpRequest req = new HttpRequest();
        req.setEndpoint(Url.getOrgDomainUrl().toExternalForm() +
                        '/services/data/v63.0/ssot/queryv2');
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setHeader('Authorization', 'Bearer ' + UserInfo.getSessionId());
        req.setBody(JSON.serialize(new Map<String, String>{ 'sql' => sql }));

        HttpResponse res = new Http().send(req);

        if (res.getStatusCode() == 200) {
            Map<String, Object> result =
                (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
            List<Object> data = (List<Object>) result.get('data');

            if (data != null) {
                for (Object row : data) {
                    List<Object> vals = (List<Object>) row;
                    OrderLineItemRA item = new OrderLineItemRA();
                    item.productID   = vals.size() > 0 && vals[0] != null
                                       ? String.valueOf(vals[0]) : null;
                    item.productName = vals.size() > 1 && vals[1] != null
                                       ? String.valueOf(vals[1]) : null;
                    item.unitPrice   = vals.size() > 2 && vals[2] != null
                                       ? Decimal.valueOf(String.valueOf(vals[2])) : null;
                    items.add(item);
                }
            }
        }

        return items;
    }
}
