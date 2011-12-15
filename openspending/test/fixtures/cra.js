{
  "dataset": {
    "name": "cra",
    "label": "Country Regional Analysis v2009",
    "description": "The Country Regional Analysis published by HM Treasury (2010 version).\n\nSource data can be found in the [CKAN data package](http://ckan.net/package/ukgov-finances-cra)",
    "currency": "GBP"
  },
  "mapping": {
    "from.name": {"column": "from.name"},
    "from.label": {"column": "from.label"},
    "from.description": {"column": "from.description"},
    "to.name": {"column": "to.name"},
    "to.label": {"column": "to.label"},
    "to.description": {"column": "to.description"},
    "time": {"column": "time.from.year"},
    "amount": {"column": "amount"},
    "total": {"column": "amount"},
    "cap_or_cur": {"column": "cap_or_cur"},
    "region": {"column": "region"},
    "name": {"column": "name"},
    "currency": {"column": "currency"},
    "population2006": {"column": "population2006"},
    "pog.name": {"column": "pog.name"},
    "pog.label": {"column": "pog.label"},
    "cofog1.name": {"column": "cofog1.name"},
    "cofog1.label": {"column": "cofog1.label"},
    "cofog1.description": {"column": "cofog1.description"},
    "cofog1.level": {"column": "cofog1.level"},
    "cofog1.change_date": {"column": "cofog1.change_date"},
    "cofog2.name": {"column": "cofog2.name"},
    "cofog2.label": {"column": "cofog2.label"},
    "cofog2.description": {"column": "cofog2.description"},
    "cofog2.level": {"column": "cofog2.level"},
    "cofog2.change_date": {"column": "cofog2.change_date"},
    "cofog3.name": {"column": "cofog3.name"},
    "cofog3.label": {"column": "cofog3.label"},
    "cofog3.description": {"column": "cofog3.description"},
    "cofog3.level": {"column": "cofog3.level"},
    "cofog3.change_date": {"column": "cofog3.change_date"}
  },
  "dimensions": {
    "from": {
      "type": "entity",
      "attributes": {
        "name": {"datatype": "string"},
        "label": {"datatype": "string"},
        "description": {"datatype": "string", 
          "default_value": ""}
      },
      "label": "Paid by",
      "description": "The entity that the money was paid from."
    },
    "to": {
      "type": "entity",
      "attributes": {
        "name": {"datatype": "string"},
        "label": {"datatype": "string"},
        "description": {"datatype": "string"}
      },
      "label": "Paid to",
      "description": "The entity that the money was paid to"
    },
    "time": {
      "type": "value",
      "label": "Tax year",
      "description": "The accounting period in which the spending happened",
      "datatype": "date"
    },
    "amount": {
      "label": "",
      "description": "",
      "datatype": "float",
      "type": "value"
    },
    "total": {
      "label": "",
      "description": "",
      "datatype": "float",
      "type": "measure"
    },
    "cap_or_cur": {
      "label": "CG, LG or PC",
      "description": "Central government, local government or public corporation",
      "datatype": "string",
      "type": "value"
    },
    "region": {
      "label": "Region",
      "description": "",
      "datatype": "string",
      "type": "value",
      "facet": true
    },
    "name": {
      "label": "Name",
      "description": "",
      "datatype": "string",
      "type": "value",
      "key": true
    },
    "currency": {
      "label": "Currency",
      "description": "",
      "datatype": "string",
      "type": "value"
    },
    "population2006": {
      "label": "Population in 2006",
      "description": "",
      "datatype": "float",
      "type": "value"
    },
    "pog": {
      "type": "classifier",
      "attributes": {
        "name": {"datatype": "string"},
        "label": {"datatype": "string"}
      },
      "label": "Programme Object Group",
      "taxonomy": "pog"
    },
    "cofog1": {
      "type": "classifier",
      "attributes": {
        "name": {"datatype": "string", 
          "default_value": "XX"},
        "label": {"datatype": "string", 
          "default_value": "(Undefined)"},
        "description": {"datatype": "string", 
          "default_value": ""},
        "level": {"datatype": "string", 
          "default_value": ""},
        "change_date": {"datatype": "string", 
          "default_value": ""}
      },
      "label": "COFOG level 1",
      "description": "Classification Of Function Of Government, level 1",
      "taxonomy": "cofog",
      "facet": true
    },
    "cofog2": {
      "type": "classifier",
      "attributes": {
        "name": {"datatype": "string", "default_value": "XX.X"},
        "label": {"datatype": "string", "default_value": "(Undefined)"},
        "description": {"datatype": "string", "default_value": ""},
        "level": {"datatype": "string", "default_value": ""},
        "change_date": {"datatype": "string", "default_value": ""}
      },
      "label": "COFOG level 2",
      "description": "Classification Of Function Of Government, level 2",
      "taxonomy": "cofog"
    },
    "cofog3": {
      "type": "classifier",
      "attributes": {
        "name": {"datatype": "string", "default_value": "XX.X.X"},
        "label": {"datatype": "string", "default_value": "(Undefined)"},
        "description": {"datatype": "string", "default_value": ""},
        "level": {"datatype": "string", "default_value": ""},
        "change_date": {"datatype": "string", "default_value": ""}
      },
      "label": "COFOG level 3",
      "description": "Classification Of Function Of Government, level 3",
      "taxonomy": "cofog"
    }
  },
  "views": [
    {
      "entity": "dataset",
      "label": "Spending by primary function",
      "name": "default",
      "dimension": "dataset",
      "breakdown": "cofog1",
      "filters": {"name": "cra"}
    },
    {
      "entity": "dataset",
      "label": "Spending by region",
      "name": "region",
      "dimension": "dataset",
      "breakdown": "region",
      "filters": {"name": "cra"}
    },
    {
      "entity": "classifier",
      "label": "Spending by region (within primary function)",
      "name": "default",
      "dimension": "cofog1",
      "breakdown": "region",
      "filters": {"taxonomy": "cofog"}
    },
    {
      "entity": "entity",
      "label": "Spending by region (within department)",
      "name": "default",
      "dimension": "from",
      "breakdown": "region",
      "filters": {"gov_department": "true"}
    }
  ]
}
