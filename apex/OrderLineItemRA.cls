public class OrderLineItemRA {
    public OrderLineItemRA() {}

    @AuraEnabled @InvocableVariable public String productID;
    @AuraEnabled @InvocableVariable public String productName;
    @AuraEnabled @InvocableVariable public Decimal unitPrice;
}
